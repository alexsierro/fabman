from django.urls import path

from legacy.views import user, user2, usage, items, check

app_name = 'legacy'
urlpatterns = [
    path('user/<uid>', user, name='user'),
    path('user2/<uid>', user2, name='user2'),
    path('usage/<resource>/<user>/<time>', usage, name='usage'),
    path('usage/<resource>/<user>/<time>/<project>', usage, name='usage'),
    path('items/', items, name='items'),
    path('check/<api_key>/<name>/<surname>', check, name='check')
]
