from django.db import models


class TestModel1(models.Model):
    a = models.CharField(max_length=50)
    b = models.IntegerField()


class TestModel2(models.Model):
    m1 = models.ForeignKey(TestModel1)
    c = models.IntegerField()


class TestM2M(models.Model):
    a = models.CharField(max_length=50)
    m2s = models.ManyToManyField(TestModel2)


class BlogUser(models.Model):
    username = models.CharField(max_length=200)


class BlogPost(models.Model):
    title = models.CharField(max_length=200)
    body = models.TextField()
    published = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(BlogUser)
