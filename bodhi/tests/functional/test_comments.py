import unittest

from nose.tools import eq_, raises
from datetime import datetime, timedelta
from webtest import TestApp

import bodhi.tests.functional.base

from bodhi import main
from bodhi.config import config
from bodhi.models import (
    Base,
    Bug,
    Build,
    CVE,
    DBSession,
    Group,
    Package,
    Release,
    Comment,
    Update,
    UpdateType,
    User,
    UpdateStatus,
    UpdateRequest,
)


class TestCommentsService(bodhi.tests.functional.base.BaseWSGICase):

    def make_comment(self,
                     update='bodhi-2.0-1.fc17',
                     text='Test',
                     karma=0,
                     **kwargs):
        comment = {
            u'update': update,
            u'text': text,
            u'karma': karma,
        }
        comment.update(kwargs)
        return comment

    def test_invalid_update(self):
        session = DBSession()
        res = self.app.post_json('/comments/', self.make_comment(
            update='bodhi-1.0-2.fc17',
        ), status=404)
        self.assertEquals(res.json_body['errors'][0]['name'], 'update')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          "Invalid update specified: bodhi-1.0-2.fc17")

    def test_invalid_karma(self):
        res = self.app.post_json('/comments/',
                                 self.make_comment(karma=-2),
                                 status=400)
        assert '-2 is less than minimum value -1' in res, res
        res = self.app.post_json('/comments/',
                                 self.make_comment(karma=2),
                                 status=400)
        assert '2 is greater than maximum value 1' in res, res

    def test_anonymous_commenting_with_login(self):
        res = self.app.post_json('/comments/', self.make_comment())
        self.assertNotIn('errors', res.json_body)
        self.assertIn('comment', res.json_body)
        self.assertEquals(res.json_body['comment']['anonymous'], False)
        self.assertEquals(res.json_body['comment']['text'], 'Test')
        self.assertEquals(res.json_body['comment']['user_id'], 1)

    #def test_anonymous_commenting_without_email(self):
    #    settings = self.app_settings.copy()
    #    app = TestApp(main({}, testing=None, **settings))
    #    res = app.post_json('/comments/', self.make_comment(), status=400)
    #    self.assertNotIn('errors', res.json_body)
    #    raise NotImplementError("check more here")

    def test_anonymous_commenting_with_email(self):
        res = self.app.post_json('/comments/',
                                 self.make_comment(email='w@t.com'))
        self.assertNotIn('errors', res.json_body)
        self.assertIn('comment', res.json_body)
        self.assertEquals(res.json_body['comment']['anonymous'], True)
        self.assertEquals(res.json_body['comment']['text'], 'Test')
        self.assertEquals(res.json_body['comment']['user_id'], 2)

    def test_anonymous_commenting_with_invalid_email(self):
        res = self.app.post_json('/comments/',
                                 self.make_comment(email='foo'),
                                 status=400)
        self.assertEquals(res.json_body['errors'][0]['name'], 'email')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          "Invalid email address")

    def test_get_single_comment(self):
        res = self.app.get('/comments/1')
        self.assertEquals(res.json_body['comment']['update_id'], 1)
        self.assertEquals(res.json_body['comment']['user_id'], 1)
        self.assertEquals(res.json_body['comment']['id'], 1)

    def test_get_single_comment_page(self):
        res = self.app.get('/comments/1', headers=dict(accept='text/html'))
        self.assertIn('libravatar.org', res)

    def test_404(self):
        self.app.get('/comments/a', status=400)

    def test_list_comments(self):
        res = self.app.get('/comments/')
        body = res.json_body
        self.assertEquals(len(body['comments']), 2)

        comment = body['comments'][0]
        self.assertEquals(comment['text'], u'srsly.  pretty good.')
        self.assertEquals(comment['karma'], 0)

    def test_list_comments_pagination(self):
        # Then, test pagination
        res = self.app.get('/comments/',
                           {"rows_per_page": 1})
        body = res.json_body
        self.assertEquals(len(body['comments']), 1)
        comment1 = body['comments'][0]

        res = self.app.get('/comments/',
                           {"rows_per_page": 1, "page": 2})
        body = res.json_body
        self.assertEquals(len(body['comments']), 1)
        comment2 = body['comments'][0]

        self.assertNotEquals(comment1, comment2)

    def test_list_comments_by_since(self):
        tomorrow = datetime.now() + timedelta(days=1)
        fmt = "%Y-%m-%d %H:%M:%S"

        # Try with no comments first
        res = self.app.get('/comments/', {"since": tomorrow.strftime(fmt)})
        body = res.json_body
        self.assertEquals(len(body['comments']), 0)

        # Now change the time on one to tomorrow
        session = DBSession()
        session.query(Comment).first().timestamp = tomorrow
        session.flush()

        # And try again
        res = self.app.get('/comments/', {"since": tomorrow.strftime(fmt)})
        body = res.json_body
        self.assertEquals(len(body['comments']), 1)

        comment = body['comments'][0]
        self.assertEquals(comment['text'], u'wow. amaze.')
        self.assertEquals(comment['karma'], 1)
        self.assertEquals(comment['user']['name'], u'guest')

    def test_list_comments_by_invalid_since(self):
        res = self.app.get('/comments/', {"since": "forever"}, status=400)
        body = res.json_body
        self.assertEquals(len(body.get('comments', [])), 0)
        error = res.json_body['errors'][0]
        self.assertEquals(error['name'], 'since')
        self.assertEquals(error['description'], 'Invalid date')

    def test_list_comments_by_future_date(self):
        """test filtering by future date"""
        tomorrow = datetime.now() + timedelta(days=1)
        tomorrow = tomorrow.strftime("%Y-%m-%d %H:%M:%S")

        res = self.app.get('/comments/', {"since": tomorrow})
        body = res.json_body
        self.assertEquals(len(body['comments']), 0)

    def test_list_comments_by_anonymous(self):
        res = self.app.get('/comments/', {"anonymous": "false"})
        body = res.json_body
        self.assertEquals(len(body['comments']), 1)

        comment = body['comments'][0]
        self.assertEquals(comment['text'], u'wow. amaze.')

    def test_list_comments_by_invalid_anonymous(self):
        res = self.app.get('/comments/', {"anonymous": "lalala"}, status=400)
        body = res.json_body
        self.assertEquals(len(body.get('comments', [])), 0)
        error = res.json_body['errors'][0]
        self.assertEquals(error['name'], 'anonymous')
        proper = "is neither in ('false', '0') nor in ('true', '1')"
        self.assertEquals(error['description'], '"lalala" %s' % proper)

    def test_list_comments_by_update(self):
        res = self.app.get('/comments/', {"updates": "bodhi-2.0-1.fc17"})
        body = res.json_body
        self.assertEquals(len(body['comments']), 2)

        comment = body['comments'][0]
        self.assertEquals(comment['text'], u'srsly.  pretty good.')

    #def test_list_comments_by_update_no_comments(self):
    #    res = self.app.get('/comments/', {"updates": "bodhi-2.0-2.fc17"})
    #    body = res.json_body
    #    self.assertEquals(len(body['comments']), 0)

    def test_list_comments_by_unexisting_update(self):
        res = self.app.get('/comments/', {"updates": "flash-player"},
                           status=400)
        body = res.json_body
        self.assertEquals(res.json_body['errors'][0]['name'], 'updates')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          "Invalid updates specified: flash-player")

    def test_list_comments_by_package(self):
        res = self.app.get('/comments/', {"packages": "bodhi"})
        body = res.json_body
        self.assertEquals(len(body['comments']), 2)

        comment = body['comments'][0]
        self.assertEquals(comment['text'], u'srsly.  pretty good.')

    def test_list_comments_by_unexisting_package(self):
        res = self.app.get('/comments/', {"packages": "flash-player"},
                           status=400)
        body = res.json_body
        self.assertEquals(res.json_body['errors'][0]['name'], 'packages')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          "Invalid packages specified: flash-player")

    def test_list_comments_by_username(self):
        res = self.app.get('/comments/', {"user": "guest"})
        body = res.json_body
        self.assertEquals(len(body['comments']), 1)

        comment = body['comments'][0]
        self.assertEquals(comment['text'], u'wow. amaze.')

    def test_list_comments_by_unexisting_username(self):
        res = self.app.get('/comments/', {"user": "santa"}, status=400)
        body = res.json_body
        self.assertEquals(len(body.get('comments', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'user')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          "Invalid user specified: santa")

    def test_list_comments_by_update_owner(self):
        res = self.app.get('/comments/', {"update_owner": "guest"})
        body = res.json_body
        self.assertEquals(len(body['comments']), 2)

        comment = body['comments'][0]
        self.assertEquals(comment['text'], u'srsly.  pretty good.')

    #def test_list_comments_by_update_owner_with_none(self):
    #    res = self.app.get('/comments/', {"update_owner": "bodhi"})
    #    body = res.json_body
    #    self.assertEquals(len(body['comments']), 0)

    #    comment = body['comments'][0]
    #    self.assertNotIn('errors', body)

    def test_list_comments_by_unexisting_update_owner(self):
        res = self.app.get('/comments/', {"update_owner": "santa"}, status=400)
        body = res.json_body
        self.assertEquals(len(body.get('comments', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'update_owner')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          "Invalid user specified: santa")

    #def test_put_json_comment(self):
    #    self.app.put_json('/comments/', self.get_comment(), status=405)

    #def test_post_json_comment(self):
    #    self.app.post_json('/comments/', self.get_comment('bodhi-2.0.0-1.fc17'))

    #def test_new_comment(self):
    #    r = self.app.post_json('/comments/', self.get_comment('bodhi-2.0.0-2.fc17'))
    #    comment = r.json_body
    #    self.assertEquals(comment['title'], u'bodhi-2.0.0-2.fc17')
    #    self.assertEquals(comment['status'], u'pending')
    #    self.assertEquals(comment['request'], u'testing')
    #    self.assertEquals(comment['user']['name'], u'guest')
    #    self.assertEquals(comment['release']['name'], u'F17')
    #    self.assertEquals(comment['type'], u'bugfix')
    #    self.assertEquals(comment['severity'], u'unspecified')
    #    self.assertEquals(comment['suggest'], u'unspecified')
    #    self.assertEquals(comment['close_bugs'], True)
    #    self.assertEquals(comment['notes'], u'this is a test comment')
    #    self.assertIsNotNone(comment['date_submitted'])
    #    self.assertEquals(comment['date_modified'], None)
    #    self.assertEquals(comment['date_approved'], None)
    #    self.assertEquals(comment['date_pushed'], None)
    #    self.assertEquals(comment['locked'], False)
    #    self.assertEquals(comment['alias'], None)
    #    self.assertEquals(comment['karma'], 0)

    #def test_edit_comment(self):
    #    args = self.get_comment('bodhi-2.0.0-2.fc17')
    #    r = self.app.post_json('/comments/', args)
    #    args['edited'] = args['builds']
    #    args['builds'] = 'bodhi-2.0.0-3.fc17'
    #    r = self.app.post_json('/comments/', args)
    #    comment = r.json_body
    #    self.assertEquals(comment['title'], u'bodhi-2.0.0-3.fc17')
    #    self.assertEquals(comment['status'], u'pending')
    #    self.assertEquals(comment['request'], u'testing')
    #    self.assertEquals(comment['user']['name'], u'guest')
    #    self.assertEquals(comment['release']['name'], u'F17')
    #    self.assertEquals(comment['type'], u'bugfix')
    #    self.assertEquals(comment['severity'], u'unspecified')
    #    self.assertEquals(comment['suggest'], u'unspecified')
    #    self.assertEquals(comment['close_bugs'], True)
    #    self.assertEquals(comment['notes'], u'this is a test comment')
    #    self.assertIsNotNone(comment['date_submitted'])
    #    self.assertIsNotNone(comment['date_modified'], None)
    #    self.assertEquals(comment['date_approved'], None)
    #    self.assertEquals(comment['date_pushed'], None)
    #    self.assertEquals(comment['locked'], False)
    #    self.assertEquals(comment['alias'], None)
    #    self.assertEquals(comment['karma'], 0)
    #    self.assertEquals(comment['comments'][-1]['text'],
    #                      u'guest edited this comment. New build(s): ' +
    #                      u'bodhi-2.0.0-3.fc17. Removed build(s): bodhi-2.0.0-2.fc17.')
    #    self.assertEquals(len(comment['builds']), 1)
    #    self.assertEquals(comment['builds'][0]['nvr'], u'bodhi-2.0.0-3.fc17')
    #    self.assertEquals(DBSession.query(Build).filter_by(nvr=u'bodhi-2.0.0-2.fc17').first(), None)

    #def test_edit_stable_comment(self):
    #    """Make sure we can't edit stable comments"""
    #    nvr = 'bodhi-2.0.0-2.fc17'
    #    args = self.get_comment(nvr)
    #    r = self.app.post_json('/comments/', args, status=200)
    #    comment = DBSession.query(Comment).filter_by(title=nvr).one()
    #    comment.status = CommentStatus.stable
    #    args['edited'] = args['builds']
    #    args['builds'] = 'bodhi-2.0.0-3.fc17'
    #    r = self.app.post_json('/comments/', args, status=400)
    #    comment = r.json_body
    #    self.assertEquals(comment['status'], 'error')
    #    self.assertEquals(comment['errors'][0]['description'], "Cannot edit stable comments")

    #def test_push_untested_critpath_to_release(self):
    #    """
    #    Ensure that we cannot push an untested critpath comment directly to
    #    stable.
    #    """
    #    args = self.get_comment('kernel-3.11.5-300.fc17')
    #    args['request'] = 'stable'
    #    comment = self.app.post_json('/comments/', args).json_body
    #    self.assertTrue(comment['critpath'])
    #    self.assertEquals(comment['request'], 'testing')

    #def test_obsoletion(self):
    #    nvr = 'bodhi-2.0.0-2.fc17'
    #    args = self.get_comment(nvr)
    #    self.app.post_json('/comments/', args)
    #    comment = DBSession.query(Comment).filter_by(title=nvr).one()
    #    comment.status = CommentStatus.testing
    #    comment.request = None

    #    args = self.get_comment('bodhi-2.0.0-3.fc17')
    #    r = self.app.post_json('/comments/', args).json_body
    #    self.assertEquals(r['request'], 'testing')
    #    self.assertEquals(r['comments'][-2]['text'],
    #                      u'This comment has obsoleted bodhi-2.0.0-2.fc17, '
    #                      'and has inherited its bugs and notes.')

    #    comment = DBSession.query(Comment).filter_by(title=nvr).one()
    #    self.assertEquals(comment.status, CommentStatus.obsolete)
    #    self.assertEquals(comment.comments[-1].text,
    #                      u'This comment has been obsoleted by bodhi-2.0.0-3.fc17')

    #def test_obsoletion_with_open_request(self):
    #    nvr = 'bodhi-2.0.0-2.fc17'
    #    args = self.get_comment(nvr)
    #    self.app.post_json('/comments/', args)

    #    args = self.get_comment('bodhi-2.0.0-3.fc17')
    #    r = self.app.post_json('/comments/', args).json_body
    #    self.assertEquals(r['request'], 'testing')

    #    comment = DBSession.query(Comment).filter_by(title=nvr).one()
    #    self.assertEquals(comment.status, CommentStatus.pending)
    #    self.assertEquals(comment.request, CommentRequest.testing)

    #def test_invalid_request(self):
    #    """Test submitting an invalid request"""
    #    args = self.get_comment()
    #    resp = self.app.post_json('/comments/%s/request' % args['builds'],
    #                              {'request': 'foo'}, status=400)
    #    resp = resp.json_body
    #    eq_(resp['status'], 'error')
    #    eq_(resp['errors'][0]['description'], u'"foo" is not one of unpush, testing, obsolete, stable')

    #    # Now try with None
    #    resp = self.app.post_json('/comments/%s/request' % args['builds'],
    #                              {'request': None}, status=400)
    #    resp = resp.json_body
    #    eq_(resp['status'], 'error')
    #    eq_(resp['errors'][0]['name'], 'request')
    #    eq_(resp['errors'][0]['description'], 'Required')

    #def test_testing_request(self):
    #    """Test submitting a valid testing request"""
    #    args = self.get_comment()
    #    args['request'] = None
    #    resp = self.app.post_json('/comments/%s/request' % args['builds'],
    #                              {'request': 'testing'})
    #    eq_(resp.json['comment']['request'], 'testing')

    #def test_invalid_stable_request(self):
    #    """Test submitting a stable request for an comment that has yet to meet the stable requirements"""
    #    args = self.get_comment()
    #    resp = self.app.post_json('/comments/%s/request' % args['builds'],
    #                              {'request': 'stable'}, status=400)
    #    eq_(resp.json['status'], 'error')
    #    eq_(resp.json['errors'][0]['description'],
    #        config.get('not_yet_tested_msg'))

    #def test_stable_request_after_testing(self):
    #    """Test submitting a stable request to an comment that has met the minimum amount of time in testing"""
    #    args = self.get_comment('bodhi-2.0.0-3.fc17')
    #    resp = self.app.post_json('/comments/', args)
    #    comment = DBSession.query(Comment).filter_by(title=resp.json['title']).one()
    #    comment.status = CommentStatus.testing
    #    comment.request = None
    #    comment.comment('This comment has been pushed to testing', author='bodhi')
    #    comment.comments[-1].timestamp -= timedelta(days=7)
    #    DBSession.flush()
    #    eq_(comment.days_in_testing, 7)
    #    eq_(comment.meets_testing_requirements, True)
    #    resp = self.app.post_json('/comments/%s/request' % args['builds'],
    #                              {'request': 'stable'})
    #    eq_(resp.json['comment']['request'], 'stable')
