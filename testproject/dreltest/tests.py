from django.test import TestCase

from dreltest.models import BlogUser, BlogPost
from dreltest.models import TestModel1, TestModel2, TestM2M
import drel as d


class BlogTest(TestCase):
    def setUp(self):
        for i in range(10):
            u = BlogUser.objects.create(username="u%d" % i)
            for p in range(i):
                BlogPost.objects.create(user=u, title="p%d" % p, body="Test")

    def test_postcount(self):
        user = d.table(BlogUser)
        post = d.table(BlogPost)

        q = (user
             .leftjoin(post, post.user_id == user.id)
             .group(user.username)
             .project(user.username, d.count(post.id).label("posts")))

        counts = dict(q.all())

        for i in range(10):
            self.assertEqual(i, counts["u%d" % i])

    def test_latesttitle(self):
        user = d.table(BlogUser)
        post1 = d.table(BlogPost)
        post2 = d.table(BlogPost)

        # An interesting query that's difficult in the ORM
        q = (user
             .leftjoin(post1, post1.user == user.id)
             .leftjoin(post2,
                       (post2.user == user.id) &
                       (post1.id < post2.id))
             .where(post2.user.is_null)
             .project(user.username, post1.title))

        latest = dict(q.all())

        # u0 has no posts, so no latest post
        self.assertEqual(None, latest["u0"])

        for i in range(1, 10):
            self.assertEqual("p%d" % (i - 1), latest["u%d" % i])

        # The subquery way of doing the same thing
        q1 = (post1
              .group(post1.user)
              .project(post1.user, d.max(post1.id).label("post_id"))
              .subquery)
        q2 = (user
              .leftjoin(q1, user.id == q1.user)
              .leftjoin(post1, post1.id == q1.post_id)
              .project(user.username, post1.title))

        latest2 = dict(q2.all())
        self.assertEqual(latest, latest2)


class DrelTest(TestCase):
    def setUp(self):
        x = TestModel1.objects.create(a="x", b=1)
        TestModel2.objects.create(m1=x, c=1)
        TestModel2.objects.create(m1=x, c=2)
        TestModel2.objects.create(m1=x, c=3)
        y = TestModel1.objects.create(a="y", b=2)
        TestModel2.objects.create(m1=y, c=4)
        t1 = TestModel2.objects.create(m1=y, c=5)
        t2 = TestModel2.objects.create(m1=y, c=6)

        m1 = TestM2M.objects.create(a="m2m1")
        TestM2M.objects.create(a="m2m2")

        m1.m2s.add(t1)
        m1.m2s.add(t2)

    def test_simple(self):
        t2 = d.table(TestModel2)

        r = t2.where(t2.c > d.const(3)).project(t2.c).all()
        self.assertEqual(3, len(list(r)))

        r = t2.where(t2.c > d.const(3) + d.const(1)).project(t2.c).all()
        self.assertEqual(2, len(list(r)))

    def test_cross(self):
        t1 = d.table(TestModel1)
        t2 = d.table(TestModel2)

        results = t1.crossjoin(t2).project(t1.a, t1.b, t2.c).all()

        def _count(x):
            return x.objects.all().count()

        self.assertEqual(
            _count(TestModel1) * _count(TestModel2),
            len(list(results)))

    def test_agg(self):
        t1 = d.table(TestModel1)
        t2 = d.table(TestModel2)

        total = t2.project(d.sum(t2.c).label("total")).one()
        self.assertEqual(6 + 5 + 4 + 3 + 2 + 1, total.total)

        grouped = list(
            t2
            .leftjoin(t1, t1.id == t2.m1)
            .group(t1.a)
            .project(t1.a, d.sum(t2.c).label("total"))
            .order(d.label("total").desc)
            .all())

        self.assertEqual("y", grouped[0].a)
        self.assertEqual(6 + 5 + 4, grouped[0].total)
        self.assertEqual("x", grouped[1].a)
        self.assertEqual(3 + 2 + 1, grouped[1].total)

    def test_order(self):
        t2 = d.table(TestModel2)

        r = list(t2.project(t2.c).order(t2.c).all())
        self.assertEqual(1, r[0].c)

        r = list(t2.project(t2.c).order(t2.c.desc).all())
        self.assertEqual(6, r[0].c)

    def test_select_expr(self):
        t2 = d.table(TestModel2)

        a = t2.project((d.max(t2.c) - d.const(2)).label("total")).subquery
        r = t2.project(t2.c).where(t2.c > a).all()
        self.assertEqual(2, len(list(r)))

    def test_derived_table(self):
        t1 = d.table(TestModel1)
        t2 = d.table(TestModel2)

        a = (t2
             .project(t2.m1, d.min(t2.c).label("m"))
             .group(t2.m1)
             .subquery)

        b = (t1
             .project(t1.a, a.m)
             .join(a, a.m1 == t1.id)
             .order(a.m))

        r = list(b.all())
        self.assertEqual(2, len(r))
        self.assertEqual(1, r[0].m)
        self.assertEqual(4, r[1].m)

    def test_count(self):
        t1 = d.table(TestModel1)
        t2 = d.table(TestModel2)

        a = t1.project(d.count().label("total")).one()
        self.assertEqual(2, a.total)

        b = (t1
             .leftjoin(t2, t2.m1_id == t1.id)
             .group(t1.a)
             .project(t1.a, d.count().label("count")))

        for i in b.all():
            self.assertEqual(3, i.count)

    def test_m2m(self):
        t2 = d.table(TestModel2)
        tm = d.table(TestM2M)
        tmjoin = d.table(TestM2M.m2s)

        a = (tm
             .project(tm.a, t2.c)
             .join(tmjoin, tmjoin.testm2m == tm.id)
             .join(t2, tmjoin.testmodel2 == t2.id)
             .order(t2.c))

        l = list(a.all())
        self.assertEqual(2, len(l))
        self.assertEqual(5, l[0].c)
        self.assertEqual(6, l[1].c)
