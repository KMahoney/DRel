# DRel

Relational algebra for Django, a la ARel, SQLAlchemy. Because
sometimes you need a left join.

This (as of writing) is a young project. It probably has bugs. The
interface may also change drastically between versions.


## Why not just use SQLAlchemy?

I highly recommend using SQLAlchemy! However, you may find this
project useful if the decision to use the Django ORM is out of your
control, or if you like the benefits of sticking with the Django ORM
(admin etc.) but would occasionally like to dip down into something
lower level that it can't express easily.


## Basic use

Given the following Models:

    class BlogUser(models.Model):
        username = models.CharField(max_length=200)

    class BlogPost(models.Model):
        title = models.CharField(max_length=200)
        body = models.TextField()
        published = models.DateTimeField(auto_now_add=True)
        user = models.ForeignKey(BlogUser)

First, create a wrapper around them:

    import drel as d
    user = d.table(BlogUser)
    post = d.table(BlogPost)

All DRel constructs are *immutable* and *stateless*, and so can be
used at the module level.

Table fields can be referenced using their Django Model name, or their
database column name.

The basic way to construct a query from a DRel table is using the
`.project(*expressions)`, `.join(table, expression)`,
`.leftjoin(table, expression)`, `.crossjoin(table)`,
`.where(expression)`, `.group(*expressions)`, `.order(*expressions)`
methods. Select queries can themselves be used as an expression or
table using `.subquery`.

All fields and expressions in the `.project` list must have a name --
expressions support `.label(name)` to give them one. Labelled
expressions can be referred to in other parts of the query using
`d.label(name)`.

Expressions have operator overloading to support comparison, arithmetic, and
(`&`), or (`|`).

Insert values into your queries with `d.const(value)`.

Evaluate your queries with `.all()` or `.one()`. `.all()` returns a
generator yielding named tuples.


## Examples

Some example queries using the Blog models.

    # All titles
    post.project(post.title).all()
    
    # All posts with usernames
    post.join(user, user.id == post.user_id)
        .project(post.title, user.username)
        .order(post.published.desc)
        .all()

    # Post counts
    user.leftjoin(post, post.user_id == user.id)
        .group(user.username)
        .project(user.username, d.count(post.id).label("postcount")))
        .all()
        
    # Total posts
    post.project(d.count().label("total")).one()

    # Latest post titles for all users
    # Use another table for a self join
    post2 = d.table(BlogPost)
    
    user.leftjoin(post, post.user == user.id)
        .leftjoin(post2, (post2.user == user.id) & (post.published < post2.published))
        .where(post2.user.is_null)
        .project(user.username, post.title)
        .all()


## TODO

* Missing SQL expressiveness
* Inserts
* Updates
* Documentation
* More tests


## License

Copyright (c) 2011, Kevin Mahoney

All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are
met:

* Redistributions of source code must retain the above copyright notice,
this list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright
notice, this list of conditions and the following disclaimer in the
documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
"AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
