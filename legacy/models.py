from django.db import models


# Create your models here.
class CheckKey(models.Model):
    description = models.CharField(max_length=200)
    key = models.CharField(max_length=200)

    def __str__(self):
        return self.description
