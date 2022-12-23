from django.urls import path

from legacy.views import user, user2, usage, items, items2, check, projects

app_name = 'legacy'
urlpatterns = [
    path('user/<uid>', user, name='user'),
    path('user2/<uid>', user2, name='user2'),
    path('usage/<resource>/<visa>/<time>', usage, name='usage'),
    path('usage/<resource>/<visa>/<time>/<project>', usage, name='usage'),
    path('items', items, name='items'),
    path('items2', items2, name='items2'),
    path('projects/<visa>', projects, name='projects'),
    path('check/<api_key>/<email>', check, name='check')
]
