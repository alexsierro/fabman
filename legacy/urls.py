from django.urls import path

from legacy.views import user, user2, usage, items, check, projects

app_name = 'legacy'
urlpatterns = [
    path('user/<uid>', user, name='user'),
    path('user2/<uid>', user2, name='user2'),
    path('usage/<resource>/<visa>/<time>', usage, name='usage'),
    path('usage/<resource>/<visa>/<time>/<project>', usage, name='usage'),
    path('items/', items, name='items'),
    path('projects/<visa>', projects, name='projects'),
    path('check/<api_key>/<name>/<surname>', check, name='check')
]
