import os
import sys

sys.path.insert(0, '/home/jvp-djur/shihta.jvp-djurdjevac.hr/repositories/radixJVD/JVD_app')

os.environ['DJANGO_SETTINGS_MODULE'] = 'JVD_app.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
