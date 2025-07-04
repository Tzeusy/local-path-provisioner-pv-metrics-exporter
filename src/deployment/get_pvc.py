from kubernetes import client, utils
from prometheus_client import CollectorRegistry, push_to_gateway
import prometheus_client as prom
import incluster_config, helper,time, os, shutil
from logger import get_logger


v1 = client.CoreV1Api(client.ApiClient(incluster_config.load_incluster_config()))
registry = CollectorRegistry()
logger = get_logger()
pvcs = v1.list_persistent_volume_claim_for_all_namespaces(watch=False)
gauge = prom.Gauge('local_volume_stats_capacity_bytes', 'local volume capacity', ['persistentvolumeclaim','node'], registry=registry)
node_list = []
all_pvc_list = []

try:
  os.environ["STORAGE_CLASS_NAME"]
except KeyError:
  logger.warning("STORAGE_CLASS_NAME was not set, defaulting to local-path")
  storageClass = "local-path"
else:
  storageClass = os.environ["STORAGE_CLASS_NAME"]
try:
  os.environ["PUSHGATEWAY_ADDRESS"]
except KeyError:
  try:
     os.environ["PUSHGATEWAY_PROMETHEUS_PUSHGATEWAY_SERVICE_HOST"]
     logger.warning("PUSHGATEWAY_ADDRESS was not set, defaulting to PUSHGATEWAY_PROMETHEUS_PUSHGATEWAY_SERVICE_HOST:PUSHGATEWAY_PROMETHEUS_PUSHGATEWAY_SERVICE_PORT")
     registryAddress = os.environ["PUSHGATEWAY_PROMETHEUS_PUSHGATEWAY_SERVICE_HOST"] + ":" + os.environ["PUSHGATEWAY_PROMETHEUS_PUSHGATEWAY_SERVICE_PORT"]
  except KeyError:
    logger.error("PUSHGATEWAY_ADDRESS and PUSHGATEWAY_PROMETHEUS_PUSHGATEWAY_SERVICE_HOST were not set, exiting") 
    exit(1)
else:
  registryAddress = os.environ["PUSHGATEWAY_ADDRESS"]
try:
  os.environ["JOB_LOG_LEVEL"]
except KeyError:
  logger.warning("JOB_LOG_LEVEL was not set, defaulting to DEBUG")
  jobloglevel = "DEBUG"
else:
  logger.warning("JOB_LOG_LEVEL was set: " + os.environ["JOB_LOG_LEVEL"].upper())
  jobloglevel = os.environ["JOB_LOG_LEVEL"].upper()
try:
  os.environ["NAMESPACE"]
  nameSpace = os.environ["NAMESPACE"]
except KeyError:
  logger.error("NAMESPACE was not set, exiting")
  exit(1)
try:
  os.environ["VOLUMEPROVISIONPATH"]
except KeyError:
  logger.warning("VOLUMEPROVISIONPATH was not set, defaulting to '/opt/local-path-provisioner'")
  volumeProvisionPath = "/opt/local-path-provisioner"
else:
  volumeProvisionPath = os.environ["VOLUMEPROVISIONPATH"]

jobImage = os.getenv('EXPORTER_JOB_IMAGE')
if jobImage is None:
  raise ValueError('Please export the EXPORTER_JOB_IMAGE environment variable')

while True:
  logger.info("Sleeping for 10 seconds...")
  time.sleep(10)

  pvcs = v1.list_persistent_volume_claim_for_all_namespaces(watch=False)

  all_pvc_list = []
  all_pvc_list_string = []
  node_list = []
  
  logger.debug("storageClass: " + storageClass + " registryAddress: " + registryAddress)

  for pvc in pvcs.items:
    logger.debug("PVC: " + pvc.metadata.name + " in namespace: " + pvc.metadata.namespace + " has storage class: " + pvc.spec.storage_class_name)
    if pvc.spec.storage_class_name == storageClass:
      if pvc.status.phase == "Bound":

        capacity = helper.convert_size_string_to_bytes(pvc.spec.resources.requests['storage'])
        gauge.labels(pvc.metadata.name,pvc.metadata.annotations['volume.kubernetes.io/selected-node']).set(capacity)
        jobName = "capacity_metrics"
        push_to_gateway(registryAddress, job=jobName, registry=registry)
        logger.debug("Pushed to registry: " + registryAddress + " job: projectbeta")
  
        if pvc.metadata.annotations['volume.kubernetes.io/selected-node'] not in node_list:
          node_list += [pvc.metadata.annotations['volume.kubernetes.io/selected-node']]
  
        all_pvc_list += [pvc.metadata.name]
      else:
        logger.debug("Ignored...")
  
  all_pvc_list_string = ",".join(all_pvc_list)
  logger.debug("all_pvc_list_string: " + all_pvc_list_string)
  logger.debug("node_list: " + str(node_list))
  
  for node in node_list:
  
    k8s_client = client.ApiClient(incluster_config.load_incluster_config())

    # TODO: Instead of template, we should construct the object directly using the client library.
    shutil.copyfile("templates/job.yaml","job.yaml")
  
    yaml_file = 'job.yaml'
  
    fin = open(yaml_file, "rt")
    data = fin.read()
    data = data.replace('NODES', node)
    data = data.replace('CLAIMS', all_pvc_list_string)
    data = data.replace('JOBLOGLEVEL', jobloglevel)
    data = data.replace('PGWADRESS', registryAddress)
    data = data.replace('VMPPATH', volumeProvisionPath)
    data = data.replace('EXPORTER_JOB_IMAGE', jobImage)
    fin.close()
    fin = open(yaml_file, "wt")
    fin.write(data)
    fin.close()
  
    utils.create_from_yaml(k8s_client,yaml_file,namespace=nameSpace)

    # TODO: Write a loop to check if the jobs are completed

  logger.info("Sleeping for 30 seconds...")
  time.sleep(30)

  
