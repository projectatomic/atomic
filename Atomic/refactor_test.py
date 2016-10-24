from Atomic.backends._docker import DockerBackend
from Atomic.backends._ostree import OSTreeBackend

from Atomic.backendutils import BackendUtils
from Atomic.objects.image import Image
from Atomic.objects.layer import Layer
import sys

ad = DockerBackend()
#print(ad.inspect_image('registry.access.redhat.com/rhel7'))
#print(ad.backend_type)
#print(ad.has_image('registry.access.redhat.com/rhel7'))
#
#print(ad.has_image('98a88a8b722a71835dd761c88451c681a8f1bc6e577f90d4dc8b234100bd4861'))

ot = OSTreeBackend()
print(vars(ot.syscontainers.args))
print("user: %s" % ot.syscontainers.user)
print("args user: %s" % ot.syscontainers.args.user)
print(ot.has_image('busybox'))
print("user: %s" % ot.syscontainers.user)
print("@@")

beu = BackendUtils()
print(beu.get_backend_for_image('busybox'))
sys.exit()
#be = beu.get_backend_for_image('registry.access.redhat.com/rhel7')
be = beu.get_backend_for_image('busybox')
#print(be.backend_type, be.input)
#image_object = be.inspect_image_object(be.input)
#print(image_object.id)
#image_object.dump()

#con_object = be.inspect_container_object("31f")
#print(con_object.status)

#for i in be.get_images_objects():
#    print(i.id)

#for i in be.get_containers_objects():
#    print(i.id)

#be = beu.get_backend_for_container("31f")
#container_object = be.inspect_container_object(be.input)
#print(container_object.status)

#ad = DockerBackend()
#print(ad.start_container("31f"))
#print(ad.stop_container("31f"))

#be = beu.get_backend_for_image('alpine')
#img_obj = ad.inspect_container('9e8')
#img_obj.dump()
#print(ad._interactive(img_obj))
#img_obj = be.inspect_image_object('alpine')
#for i in be.get_containers_by_image(img_obj):
#    print(i.id)
#
#be.delete_containers_by_image(img_obj, force=True)

#img_obj = ad.inspect_image('alpine')
#img_obj.dump()


#layer_obj = Layer(img_obj)
#layer_obj.dump()

#print(img_obj.backend)
#print(img_obj.backend.backend_type)
#print(img_obj.input_name)
#print(img_obj.fq_name)
#print(img_obj.fq_name)

#objs = ad.get_images()
#deep_objs = []
#for o in objs:
#    deep_objs.append(o._to_deep())

