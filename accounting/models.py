from django.db import models


class Account(models.Model):
    number = models.IntegerField(null=False, blank=False)
    name = models.CharField(max_length=200, default=None, null=False, blank=False)

    def __str__(self):
        return f'{self.number} - {self.name}'
