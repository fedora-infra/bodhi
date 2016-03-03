# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import mock
from datetime import datetime, timedelta

import bodhi.tests.functional.base

from bodhi.models import (
    Comment,
    Release,
    User,
    Update,
    UpdateRequest,
    UpdateStatus,
    UpdateType,
)

someone_elses_update = up2 = u'bodhi-2.0-200.fc17'

class TestCommentsService(bodhi.tests.functional.base.BaseWSGICase):
    def setUp(self, *args, **kwargs):
        super(TestCommentsService, self).setUp(*args, **kwargs)

        # Add a second update owned by somebody else so we can test karma
        # policy stuff
        user2 = User(name=u'lmacken')
        self.db.flush()
        self.db.add(user2)
        release = self.db.query(Release).filter_by(name=u'F17').one()
        update = Update(
            title=someone_elses_update,
            #builds=[build],
            user=user2,
            request=UpdateRequest.testing,
            type=UpdateType.enhancement,
            notes=u'Useful details!',
            release=release,
            date_submitted=datetime(1984, 11, 02),
            requirements=u'rpmlint',
            stable_karma=3,
            unstable_karma=-3,
        )
        self.db.add(update)
        self.db.flush()

    def make_comment(self,
                     update='bodhi-2.0-1.fc17',
                     text='Test',
                     karma=0,
                     **kwargs):
        comment = {
            u'update': update,
            u'text': text,
            u'karma': karma,
            u'csrf_token': self.get_csrf_token(),
        }
        comment.update(kwargs)
        return comment

    def test_invalid_update(self):
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

    @mock.patch('bodhi.notifications.publish')
    def test_commenting_with_critpath_feedback(self, publish):
        comment = self.make_comment()
        comment['karma_critpath'] = -1  # roll out the trucks
        res = self.app.post_json('/comments/', comment)
        self.assertNotIn('errors', res.json_body)
        self.assertIn('comment', res.json_body)
        self.assertEquals(res.json_body['comment']['anonymous'], False)
        self.assertEquals(res.json_body['comment']['text'], 'Test')
        self.assertEquals(res.json_body['comment']['user_id'], 1)
        self.assertEquals(res.json_body['comment']['karma_critpath'], -1)
        publish.assert_called_once_with(topic='update.comment', msg=mock.ANY)

    @mock.patch('bodhi.notifications.publish')
    def test_commenting_with_bug_feedback(self, publish):
        comment = self.make_comment()
        comment['bug_feedback'] = [{'bug_id': 12345, 'karma': 1}]
        res = self.app.post_json('/comments/', comment)
        self.assertNotIn('errors', res.json_body)
        self.assertIn('comment', res.json_body)
        self.assertEquals(res.json_body['comment']['anonymous'], False)
        self.assertEquals(res.json_body['comment']['text'], 'Test')
        self.assertEquals(res.json_body['comment']['user_id'], 1)
        self.assertIn('bug_feedback', res.json_body['comment'])
        feedback = res.json_body['comment']['bug_feedback']
        self.assertEquals(len(feedback), 1)
        publish.assert_called_once_with(topic='update.comment', msg=mock.ANY)

    @mock.patch('bodhi.notifications.publish')
    def test_commenting_with_testcase_feedback(self, publish):
        comment = self.make_comment()
        comment['testcase_feedback'] = [{'testcase_name': "Wat", 'karma': -1}]
        res = self.app.post_json('/comments/', comment)
        self.assertNotIn('errors', res.json_body)
        self.assertIn('comment', res.json_body)
        self.assertEquals(res.json_body['comment']['anonymous'], False)
        self.assertEquals(res.json_body['comment']['text'], 'Test')
        self.assertEquals(res.json_body['comment']['user_id'], 1)
        self.assertIn('testcase_feedback', res.json_body['comment'])
        feedback = res.json_body['comment']['testcase_feedback']
        self.assertEquals(len(feedback), 1)
        publish.assert_called_once_with(topic='update.comment', msg=mock.ANY)

    @mock.patch('bodhi.notifications.publish')
    def test_commenting_with_login(self, publish):
        res = self.app.post_json('/comments/', self.make_comment())
        self.assertNotIn('errors', res.json_body)
        self.assertIn('comment', res.json_body)
        self.assertEquals(res.json_body['comment']['anonymous'], False)
        self.assertEquals(res.json_body['comment']['text'], 'Test')
        self.assertEquals(res.json_body['comment']['user_id'], 1)
        publish.assert_called_once_with(topic='update.comment', msg=mock.ANY)

    @mock.patch('bodhi.notifications.publish')
    def test_commenting_twice_with_neutral_karma(self, publish):
        res = self.app.post_json('/comments/', self.make_comment())
        self.assertNotIn('errors', res.json_body)
        self.assertIn('comment', res.json_body)
        self.assertEquals(res.json_body['comment']['anonymous'], False)
        self.assertEquals(res.json_body['comment']['text'], 'Test')
        self.assertEquals(res.json_body['comment']['user_id'], 1)
        publish.assert_called_once_with(topic='update.comment', msg=mock.ANY)

        res = self.app.post_json('/comments/', self.make_comment())
        self.assertNotIn('errors', res.json_body)
        self.assertIn('comment', res.json_body)
        self.assertEquals(res.json_body['comment']['anonymous'], False)
        self.assertEquals(res.json_body['comment']['text'], 'Test')
        self.assertEquals(res.json_body['comment']['user_id'], 1)
        self.assertEquals(publish.call_count, 2)

    @mock.patch('bodhi.notifications.publish')
    def test_commenting_twice_with_double_positive_karma(self, publish):
        res = self.app.post_json('/comments/', self.make_comment(up2, karma=1))
        self.assertNotIn('errors', res.json_body)
        self.assertIn('comment', res.json_body)
        self.assertEquals(res.json_body['comment']['anonymous'], False)
        self.assertEquals(res.json_body['comment']['text'], 'Test')
        self.assertEquals(res.json_body['comment']['user_id'], 1)
        self.assertEquals(res.json_body['comment']['karma'], 1)
        publish.assert_called_once_with(topic='update.comment', msg=mock.ANY)
        self.assertEquals(res.json_body['comment']['update']['karma'], 1)

        res = self.app.post_json('/comments/', self.make_comment(up2, karma=1))
        self.assertNotIn('errors', res.json_body)
        self.assertIn('comment', res.json_body)
        self.assertEquals(res.json_body['comment']['anonymous'], False)
        self.assertEquals(res.json_body['comment']['text'], 'Test')
        self.assertEquals(res.json_body['comment']['user_id'], 1)
        self.assertEquals(publish.call_count, 2)

        # Mainly, ensure that the karma didn't increase *again*
        self.assertEquals(res.json_body['comment']['update']['karma'], 1)
        # A caveat message might be nice?  not necessary at this point...
        #self.assertEquals(res.json_body['caveats'][0]['description'],
        #                  'lol, you cant double up son')

    @mock.patch('bodhi.notifications.publish')
    def test_commenting_twice_with_positive_then_negative_karma(self, publish):
        res = self.app.post_json('/comments/', self.make_comment(up2, karma=1))
        self.assertNotIn('errors', res.json_body)
        self.assertIn('comment', res.json_body)
        self.assertEquals(res.json_body['comment']['anonymous'], False)
        self.assertEquals(res.json_body['comment']['text'], 'Test')
        self.assertEquals(res.json_body['comment']['user_id'], 1)
        publish.assert_called_once_with(topic='update.comment', msg=mock.ANY)
        self.assertEquals(res.json_body['comment']['update']['karma'], 1)

        res = self.app.post_json('/comments/', self.make_comment(up2, karma=-1))
        self.assertNotIn('errors', res.json_body)
        self.assertIn('comment', res.json_body)
        self.assertEquals(res.json_body['comment']['anonymous'], False)
        self.assertEquals(res.json_body['comment']['text'], 'Test')
        self.assertEquals(res.json_body['comment']['user_id'], 1)
        self.assertEquals(publish.call_count, 2)

        # Mainly, ensure that original karma is overwritten..
        self.assertEquals(res.json_body['comment']['update']['karma'], -1)
        self.assertEquals(res.json_body['caveats'][0]['description'],
                          'Your karma standing was reversed.')

    @mock.patch('bodhi.notifications.publish')
    def test_commenting_with_negative_karma(self, publish):
        res = self.app.post_json('/comments/', self.make_comment(up2, karma=-1))
        self.assertNotIn('errors', res.json_body)
        self.assertIn('comment', res.json_body)
        self.assertEquals(res.json_body['comment']['anonymous'], False)
        self.assertEquals(res.json_body['comment']['text'], 'Test')
        self.assertEquals(res.json_body['comment']['user_id'], 1)
        publish.assert_called_once_with(topic='update.comment', msg=mock.ANY)
        self.assertEquals(res.json_body['comment']['update']['karma'], -1)

    @mock.patch('bodhi.notifications.publish')
    def test_anonymous_commenting_with_email(self, publish):
        res = self.app.post_json('/comments/',
                                 self.make_comment(email='w@t.com'))
        self.assertNotIn('errors', res.json_body)
        self.assertIn('comment', res.json_body)
        self.assertEquals(res.json_body['comment']['anonymous'], True)
        self.assertEquals(res.json_body['comment']['text'], 'Test')
        self.assertEquals(res.json_body['comment']['user_id'], 2)
        publish.assert_called_once_with(topic='update.comment', msg=mock.ANY)

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
        self.assertIn('text/html', res.headers['Content-Type'])
        self.assertIn('libravatar.org', res)

    def test_get_single_comment_jsonp(self):
        res = self.app.get('/comments/1',
                           {'callback': 'callback'},
                           headers=dict(accept='application/javascript'))
        self.assertIn('application/javascript', res.headers['Content-Type'])
        self.assertIn('callback', res)
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

    def test_list_comments_jsonp(self):
        res = self.app.get('/comments/',
                           {'callback': 'callback'},
                           headers=dict(accept='application/javascript'))
        self.assertIn('application/javascript', res.headers['Content-Type'])
        self.assertIn('callback', res)
        self.assertIn('srsly.  pretty good', res)

    def test_list_comments_rss(self):
        res = self.app.get('/rss/comments/',
                           headers=dict(accept='application/atom+xml'))
        self.assertIn('application/rss+xml', res.headers['Content-Type'])
        self.assertIn('srsly.  pretty good', res)

    def test_list_comments_page(self):
        res = self.app.get('/comments/', headers=dict(accept='text/html'))
        self.assertIn('text/html', res.headers['Content-Type'])
        self.assertIn('libravatar.org', res)

    def test_search_comments(self):
        res = self.app.get('/comments/', {'like': 'srsly'})
        body = res.json_body
        self.assertEquals(len(body['comments']), 1)

        comment = body['comments'][0]
        self.assertEquals(comment['text'], u'srsly.  pretty good.')

        res = self.app.get('/comments/', {'like': 'wat'})
        body = res.json_body
        self.assertEquals(len(body['comments']), 0)

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
        tomorrow = datetime.utcnow() + timedelta(days=1)
        fmt = "%Y-%m-%d %H:%M:%S"

        # Try with no comments first
        res = self.app.get('/comments/', {"since": tomorrow.strftime(fmt)})
        body = res.json_body
        self.assertEquals(len(body['comments']), 0)

        # Now change the time on one to tomorrow
        self.db.query(Comment).first().timestamp = tomorrow
        self.db.flush()

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
        tomorrow = datetime.utcnow() + timedelta(days=1)
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

    def test_list_comments_by_update_no_comments(self):
        nvr = u'bodhi-2.0-201.fc17'
        update = Update(
            title=nvr,
            #builds=[build],
            #user=user,
            request=UpdateRequest.testing,
            type=UpdateType.enhancement,
            notes=u'Useful details!',
            #release=release,
            date_submitted=datetime(1984, 11, 02),
            requirements=u'rpmlint',
            stable_karma=3,
            unstable_karma=-3,
        )
        self.db.add(update)
        self.db.flush()

        res = self.app.get('/comments/', {"updates": nvr})
        body = res.json_body
        self.assertEquals(len(body['comments']), 0)

    def test_list_comments_by_unexisting_update(self):
        res = self.app.get('/comments/', {"updates": "flash-player"},
                           status=400)
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

    def test_list_comments_by_update_owner_with_none(self):
        user = User(name=u'ralph')
        self.db.add(user)
        self.db.flush()
        res = self.app.get('/comments/', {"update_owner": "ralph"})
        body = res.json_body
        self.assertEquals(len(body['comments']), 0)
        self.assertNotIn('errors', body)

    def test_list_comments_by_unexisting_update_owner(self):
        res = self.app.get('/comments/', {"update_owner": "santa"}, status=400)
        body = res.json_body
        self.assertEquals(len(body.get('comments', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'update_owner')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          "Invalid user specified: santa")

    def test_list_comments_with_ignore_user(self):
        res = self.app.get('/comments/', {"ignore_user": "guest"})
        body = res.json_body
        self.assertEquals(len(body['comments']), 1)
        self.assertNotIn('errors', body)
        comment = body['comments'][0]
        self.assertEquals(comment['text'], u'srsly.  pretty good.')

    def test_list_comments_with_unexisting_ignore_user(self):
        res = self.app.get('/comments/', {"ignore_user": "santa"}, status=400)
        body = res.json_body
        self.assertEquals(len(body.get('comments', [])), 0)
        self.assertEquals(res.json_body['errors'][0]['name'], 'ignore_user')
        self.assertEquals(res.json_body['errors'][0]['description'],
                          "Invalid user specified: santa")

    def test_put_json_comment(self):
        """ We only want to POST comments, not PUT. """
        self.app.put_json('/comments/', self.make_comment(), status=405)

    def test_post_json_comment(self):
        self.app.post_json('/comments/', self.make_comment(text='awesome'))
        up = self.db.query(Update).filter_by(title='bodhi-2.0-1.fc17').one()
        self.assertEquals(len(up.comments), 3)
        self.assertEquals(up.comments[-1]['text'], 'awesome')

    def test_new_comment(self):
        comment = self.make_comment('bodhi-2.0-1.fc17', text='superb')
        r = self.app.post_json('/comments/', comment)
        comment = r.json_body['comment']
        self.assertEquals(comment['text'], u'superb')
        self.assertEquals(comment['user']['name'], u'guest')
        self.assertEquals(comment['author'], u'guest')
        self.assertEquals(comment['update']['title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(comment['update_title'], u'bodhi-2.0-1.fc17')
        self.assertEquals(comment['karma'], 0)

    def test_no_self_karma(self):
        " Make sure you can't give +1 karma to your own updates.. "
        comment = self.make_comment('bodhi-2.0-1.fc17', karma=1)
        # The author of this comment is "guest"

        up = self.db.query(Update).filter_by(title='bodhi-2.0-1.fc17').one()
        self.assertEquals(up.user.name, 'guest')

        r = self.app.post_json('/comments/', comment)
        comment = r.json_body['comment']
        self.assertEquals(comment['user']['name'], u'guest')
        self.assertEquals(comment['update']['title'], u'bodhi-2.0-1.fc17')
        caveats = r.json_body['caveats']
        self.assertEquals(len(caveats), 1)
        self.assertEquals(caveats[0]['name'], 'karma')
        self.assertEquals(caveats[0]['description'],
                          "You may not give karma to your own updates.")
        self.assertEquals(comment['karma'], 0)  # This is the real check

    def test_comment_on_locked_update(self):
        """ Make sure you can comment on locked updates. """
        # Lock it
        up = self.db.query(Update).filter_by(title=up2).one()
        up.locked = True
        up.status = UpdateStatus.testing
        up.request = None
        self.assertEquals(len(up.comments), 0)  # Before
        self.assertEquals(up.karma, 0)          # Before
        self.db.flush()

        comment = self.make_comment(up2, karma=1)
        self.app.post_json('/comments/', comment)

        up = self.db.query(Update).filter_by(title=up2).one()
        self.assertEquals(len(up.comments), 1)  # After
        self.assertEquals(up.karma, 1)          # After

    def test_comment_on_locked_update_no_threshhold_action(self):
        " Make sure you can't trigger threshold action on locked updates "
        # Lock it
        up = self.db.query(Update).filter_by(title=up2).one()
        up.locked = True
        up.status = UpdateStatus.testing
        up.request = UpdateStatus.stable
        up.stable_karma = 1
        up.unstable_karma = -1
        self.assertEquals(len(up.comments), 0)  # Before
        self.assertEquals(up.karma, 0)          # Before
        self.db.flush()

        comment = self.make_comment(up2, karma=-1)
        self.app.post_json('/comments/', comment)

        up = self.db.query(Update).filter_by(title=up2).one()
        self.assertEquals(len(up.comments), 1)  # After
        self.assertEquals(up.karma, -1)         # After
        # Ensure that the request did not change .. don't trigger something.
        self.assertEquals(up.status.value, UpdateStatus.testing.value)
        self.assertEquals(up.request.value, UpdateRequest.stable.value)
