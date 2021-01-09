from django.db import models


class ChecklistAnimator(models.Model):
    date = models.DateTimeField('date used')
    animators = models.ManyToManyField('members.Member')
