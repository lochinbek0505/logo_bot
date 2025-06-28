from django.db import models

# Create your models here.

class CheckItems(models.Model):
    image = models.ImageField(upload_to="images/checkitems/")
    audio = models.FileField(upload_to="audios/checkitems/")
    