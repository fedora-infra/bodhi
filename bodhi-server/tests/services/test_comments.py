# Copyright © 2014-2019 Red Hat, Inc. and others.
#
# This file is part of Bodhi.
#
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

from datetime import datetime, timedelta
from unittest import mock
import copy

from fedora_messaging import api, testing as fml_testing
import webtest

from bodhi.messages.schemas import update as update_schemas
from bodhi.server.models import (Build, Comment, Release, RpmBuild, RpmPackage, Update,
                                 UpdateRequest, UpdateStatus, UpdateType, User)
from bodhi.server import main
from .. import base


someone_elses_update = up2 = 'bodhi-2.0-200.fc17'


class TestCommentsService(base.BasePyTestCase):
    def setup_method(self, method):
        super(TestCommentsService, self).setup_method(method)

        # Add a second update owned by somebody else so we can test karma
        # policy stuff
        user2 = User(name='lmacken')
        self.db.flush()
        self.db.add(user2)
        release = self.db.query(Release).filter_by(name='F17').one()
        update = Update(
            user=user2,
            request=UpdateRequest.testing,
            type=UpdateType.enhancement,
            notes='Useful details!',
            release=release,
            date_submitted=datetime(1984, 11, 2),
            requirements='rpmlint',
            stable_karma=3,
            unstable_karma=-3,
        )
        self.db.add(update)
        build = RpmBuild(nvr=up2, update=update,
                         package=RpmPackage.query.filter_by(name='bodhi').one())
        self.db.add(build)
        self.db.flush()

    def make_comment(self,
                     nvr='bodhi-2.0-1.fc17',
                     text='Test',
                     karma=0,
                     **kwargs):
        update = Build.query.filter_by(nvr=nvr).one().update.alias
        comment = {
            'update': update,
            'text': text,
            'karma': karma,
            'csrf_token': self.get_csrf_token(),
        }
        comment.update(kwargs)
        return comment

    def test_invalid_update(self):
        res = self.app.post_json('/comments/', self.make_comment(
            update='bodhi-1.0-2.fc17',
        ), status=404)
        assert res.json_body['errors'][0]['name'] == 'update'
        assert res.json_body['errors'][0]['description'] == \
            "Invalid update specified: bodhi-1.0-2.fc17"

    def test_invalid_karma(self):
        res = self.app.post_json('/comments/',
                                 self.make_comment(karma=-2),
                                 status=400)
        assert '-2 is less than minimum value -1' in res
        res = self.app.post_json('/comments/',
                                 self.make_comment(karma=2),
                                 status=400)
        assert '2 is greater than maximum value 1' in res

    def test_commenting_with_critpath_feedback(self):
        comment = self.make_comment()
        comment['karma_critpath'] = -1  # roll out the trucks

        with fml_testing.mock_sends(update_schemas.UpdateCommentV1):
            res = self.app.post_json('/comments/', comment)

        assert'errors' not in res.json_body
        assert'comment' in res.json_body
        assert res.json_body['comment']['text'] == 'Test'
        assert res.json_body['comment']['user_id'] == 1
        assert res.json_body['comment']['karma_critpath'] == -1

    def test_commenting_with_bug_feedback(self):
        comment = self.make_comment()
        comment['bug_feedback.0.bug_id'] = 12345
        comment['bug_feedback.0.karma'] = 1

        with fml_testing.mock_sends(update_schemas.UpdateCommentV1):
            res = self.app.post_json('/comments/', comment)

        assert'errors' not in res.json_body
        assert 'comment' in res.json_body
        assert res.json_body['comment']['text'] == 'Test'
        assert res.json_body['comment']['user_id'] == 1
        assert'bug_feedback' in res.json_body['comment']
        feedback = res.json_body['comment']['bug_feedback']
        assert len(feedback) == 1

    def test_commenting_with_testcase_feedback(self):
        comment = self.make_comment()

        comment['testcase_feedback.0.testcase_name'] = "Wat"
        comment['testcase_feedback.0.karma'] = -1

        with fml_testing.mock_sends(update_schemas.UpdateCommentV1):
            res = self.app.post_json('/comments/', comment)

        assert 'errors' not in res.json_body
        assert 'comment' in res.json_body
        assert res.json_body['comment']['text'] == 'Test'
        assert res.json_body['comment']['user_id'] == 1
        assert'testcase_feedback' in res.json_body['comment']
        feedback = res.json_body['comment']['testcase_feedback']
        assert len(feedback) == 1

    def test_commenting_with_login(self):
        with fml_testing.mock_sends(update_schemas.UpdateCommentV1):
            res = self.app.post_json('/comments/', self.make_comment())

        assert 'errors' not in res.json_body
        assert 'comment' in res.json_body
        assert res.json_body['comment']['text'] == 'Test'
        assert res.json_body['comment']['user_id'] == 1

    def test_commenting_twice_with_neutral_karma(self):
        with fml_testing.mock_sends(update_schemas.UpdateCommentV1):
            res = self.app.post_json('/comments/', self.make_comment())

        assert 'errors' not in res.json_body
        assert 'comment' in res.json_body
        assert res.json_body['comment']['text'] == 'Test'
        assert res.json_body['comment']['user_id'] == 1

        with fml_testing.mock_sends(update_schemas.UpdateCommentV1):
            res = self.app.post_json('/comments/', self.make_comment())

        assert 'errors' not in res.json_body
        assert 'comment' in res.json_body
        assert res.json_body['comment']['text'] == 'Test'
        assert res.json_body['comment']['user_id'] == 1

    def test_commenting_twice_with_double_positive_karma(self):
        with fml_testing.mock_sends(update_schemas.UpdateCommentV1):
            res = self.app.post_json('/comments/', self.make_comment(up2, karma=1))

        assert 'errors' not in res.json_body
        assert 'comment' in res.json_body
        assert res.json_body['comment']['text'] == 'Test'
        assert res.json_body['comment']['user_id'] == 1
        assert res.json_body['comment']['karma'] == 1
        assert res.json_body['comment']['update']['karma'] == 1

        with fml_testing.mock_sends(update_schemas.UpdateCommentV1):
            res = self.app.post_json('/comments/', self.make_comment(up2, karma=1))

        assert 'errors' not in res.json_body
        assert 'comment' in res.json_body
        assert res.json_body['comment']['text'] == 'Test'
        assert res.json_body['comment']['user_id'] == 1
        # Mainly, ensure that the karma didn't increase *again*
        assert res.json_body['comment']['update']['karma'] == 1

    def test_commenting_twice_with_positive_then_negative_karma(self):
        with fml_testing.mock_sends(update_schemas.UpdateCommentV1):
            res = self.app.post_json('/comments/', self.make_comment(up2, karma=1))

        assert 'errors' not in res.json_body
        assert 'comment' in res.json_body
        assert res.json_body['comment']['text'] == 'Test'
        assert res.json_body['comment']['user_id'] == 1
        assert res.json_body['comment']['update']['karma'] == 1

        with fml_testing.mock_sends(update_schemas.UpdateCommentV1):
            res = self.app.post_json('/comments/', self.make_comment(up2, karma=-1))

        assert 'errors' not in res.json_body
        assert 'comment' in res.json_body
        assert res.json_body['comment']['text'] == 'Test'
        assert res.json_body['comment']['user_id'] == 1

        # Mainly, ensure that original karma is overwritten..
        assert res.json_body['comment']['update']['karma'] == -1
        assert res.json_body['caveats'][0]['description'] == 'Your karma standing was reversed.'

    def test_commenting_with_negative_karma(self):
        with fml_testing.mock_sends(update_schemas.UpdateCommentV1):
            res = self.app.post_json('/comments/', self.make_comment(up2, karma=-1))

        assert 'errors' not in res.json_body
        assert 'comment' in res.json_body
        assert res.json_body['comment']['text'] == 'Test'
        assert res.json_body['comment']['user_id'] == 1
        assert res.json_body['comment']['update']['karma'] == -1

    def test_empty_comment(self):
        """Ensure that a comment without text or feedback is not permitted."""
        comment = self.make_comment(text='')
        comment['bug_feedback.0.bug_id'] = 12345
        comment['bug_feedback.0.karma'] = 0
        comment['testcase_feedback.0.testcase_name'] = "Wat"
        comment['testcase_feedback.0.karma'] = 0
        res = self.app.post_json('/comments/', comment, status=400)

        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == \
            'You must provide either some text or feedback'

    @mock.patch('bodhi.server.services.comments.Update.comment',
                side_effect=IOError('IOError. oops!'))
    def test_unexpected_exception(self, exception):
        """Ensure that an unexpected Exception is handled by new_comment()."""

        res = self.app.post_json('/comments/', self.make_comment(), status=400)

        assert res.json_body['status'] == 'error'
        assert res.json_body['errors'][0]['description'] == 'Unable to create comment'

    def test_get_single_comment(self):
        res = self.app.get('/comments/1')
        assert res.json_body['comment']['update_id'] == 1
        assert res.json_body['comment']['user_id'] == 1
        assert res.json_body['comment']['id'] == 1

    def test_get_single_comment_page(self):
        res = self.app.get('/comments/1', headers=dict(accept='text/html'))
        assert 'text/html' in res.headers['Content-Type']
        assert 'libravatar.org' in res

    def test_get_single_comment_jsonp(self):
        res = self.app.get('/comments/1',
                           {'callback': 'callback'},
                           headers=dict(accept='application/javascript'))
        assert 'application/javascript' in res.headers['Content-Type']
        assert 'callback' in res
        assert 'libravatar.org' in res

    def test_404(self):
        self.app.get('/comments/a', status=400)

    def test_list_comments(self):
        res = self.app.get('/comments/')
        body = res.json_body
        assert len(body['comments']) == 2

        comment = body['comments'][0]
        assert comment['text'] == 'srsly.  pretty good.'
        assert comment['karma'] == 0

    def test_list_comments_jsonp(self):
        res = self.app.get('/comments/',
                           {'callback': 'callback'},
                           headers=dict(accept='application/javascript'))
        assert 'application/javascript' in res.headers['Content-Type']
        assert 'callback' in res
        assert 'srsly.  pretty good' in res

    def test_list_comments_rss(self):
        res = self.app.get('/rss/comments/',
                           headers=dict(accept='application/atom+xml'))
        assert 'application/rss+xml' in res.headers['Content-Type']
        assert 'srsly.  pretty good' in res

    def test_list_comments_rss_failing_condition(self):
        comment = self.db.query(Comment).first()
        comment.text = ''
        self.db.flush()

        res = self.app.get('/rss/comments/',
                           headers=dict(accept='application/atom+xml'))
        assert 'application/rss+xml' in res.headers['Content-Type']
        assert "{} comment #{}".format(comment.update.alias, comment.id) in res

    def test_list_comments_page(self):
        res = self.app.get('/comments/', headers=dict(accept='text/html'))
        assert 'text/html' in res.headers['Content-Type']
        assert 'libravatar.org' in res

    def test_search_comments(self):
        res = self.app.get('/comments/', {'like': 'srsly'})
        body = res.json_body
        assert len(body['comments']) == 1

        comment = body['comments'][0]
        assert comment['text'] == 'srsly.  pretty good.'

        res = self.app.get('/comments/', {'like': 'wat'})
        body = res.json_body
        assert len(body['comments']) == 0

    def test_list_comments_pagination(self):
        # Then, test pagination
        res = self.app.get('/comments/',
                           {"rows_per_page": 1})
        body = res.json_body
        assert len(body['comments']) == 1
        comment1 = body['comments'][0]

        res = self.app.get('/comments/',
                           {"rows_per_page": 1, "page": 2})
        body = res.json_body
        assert len(body['comments']) == 1
        comment2 = body['comments'][0]

        assert comment1 != comment2

    def test_list_comments_by_since(self):
        tomorrow = datetime.utcnow() + timedelta(days=1)
        fmt = "%Y-%m-%d %H:%M:%S"

        # Try with no comments first
        res = self.app.get('/comments/', {"since": tomorrow.strftime(fmt)})
        body = res.json_body
        assert len(body['comments']) == 0

        # Now change the time on one to tomorrow
        self.db.query(Comment).first().timestamp = tomorrow
        self.db.flush()

        # And try again
        res = self.app.get('/comments/', {"since": tomorrow.strftime(fmt)})
        body = res.json_body
        assert len(body['comments']) == 1

        comment = body['comments'][0]
        assert comment['text'] == 'wow. amaze.'
        assert comment['karma'] == 1
        assert comment['user']['name'] == 'guest'

    def test_list_comments_by_invalid_since(self):
        res = self.app.get('/comments/', {"since": "forever"}, status=400)
        body = res.json_body
        assert len(body.get('comments', [])) == 0
        error = res.json_body['errors'][0]
        assert error['name'] == 'since'
        assert error['description'] == 'Invalid date'

    def test_list_comments_by_future_date(self):
        """test filtering by future date"""
        tomorrow = datetime.utcnow() + timedelta(days=1)
        tomorrow = tomorrow.strftime("%Y-%m-%d %H:%M:%S")

        res = self.app.get('/comments/', {"since": tomorrow})
        body = res.json_body
        assert len(body['comments']) == 0

    def test_list_comments_by_update(self):
        alias = Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update.alias

        res = self.app.get('/comments/', {"updates": alias})

        body = res.json_body
        assert len(body['comments']) == 2

        comment = body['comments'][0]
        assert comment['text'] == 'srsly.  pretty good.'

    def test_list_comments_by_update_no_comments(self):
        update = Update(
            request=UpdateRequest.testing,
            type=UpdateType.enhancement,
            notes='Useful details!',
            date_submitted=datetime(1984, 11, 2),
            requirements='rpmlint',
            stable_karma=3,
            unstable_karma=-3,
            release=Release.query.one()
        )
        self.db.add(update)
        self.db.flush()

        res = self.app.get('/comments/', {"updates": update.alias})

        body = res.json_body
        assert len(body['comments']) == 0

    def test_list_comments_by_nonexistent_update(self):
        res = self.app.get('/comments/', {"updates": "flash-player"},
                           status=400)
        assert res.json_body['errors'][0]['name'] == 'updates'
        assert res.json_body['errors'][0]['description'] == \
            "Invalid updates specified: flash-player"

    def test_list_comments_by_package(self):
        res = self.app.get('/comments/', {"packages": "bodhi"})
        body = res.json_body
        assert len(body['comments']) == 2

        comment = body['comments'][0]
        assert comment['text'] == 'srsly.  pretty good.'

    def test_list_comments_by_nonexistent_package(self):
        res = self.app.get('/comments/', {"packages": "flash-player"},
                           status=400)
        assert res.json_body['errors'][0]['name'] == 'packages'
        assert res.json_body['errors'][0]['description'] == \
            "Invalid packages specified: flash-player"

    def test_list_comments_by_username(self):
        res = self.app.get('/comments/', {"user": "guest"})
        body = res.json_body
        assert len(body['comments']) == 1

        comment = body['comments'][0]
        assert comment['text'] == 'wow. amaze.'

    def test_list_comments_by_multiple_usernames(self):
        update = Update(
            request=UpdateRequest.testing,
            type=UpdateType.enhancement,
            notes='Just another update.',
            date_submitted=datetime(1981, 10, 11),
            requirements='rpmlint',
            stable_karma=3,
            unstable_karma=-3,
            release=Release.query.one()
        )
        self.db.add(update)

        another_user = User(name='aUser')
        self.db.add(another_user)

        comment = Comment(karma=1, text='Cool! 😃')
        comment.user = another_user
        self.db.add(comment)
        update.comments.append(comment)
        self.db.flush()

        res = self.app.get('/comments/', {"user": "guest,aUser"})
        body = res.json_body
        assert len(body['comments']) == 2
        assert body['comments'][0]['text'] == 'Cool! 😃'
        assert body['comments'][1]['text'] == 'wow. amaze.'

    def test_list_comments_by_nonexistent_username(self):
        res = self.app.get('/comments/', {"user": "santa"}, status=400)
        body = res.json_body
        assert len(body.get('comments', [])) == 0
        assert res.json_body['errors'][0]['name'] == 'user'
        assert res.json_body['errors'][0]['description'] == "Invalid users specified: santa"

    def test_list_comments_by_update_owner(self):
        res = self.app.get('/comments/', {"update_owner": "guest"})
        body = res.json_body
        assert len(body['comments']) == 2

        comment = body['comments'][0]
        assert comment['text'] == 'srsly.  pretty good.'

    def test_list_comments_by_multiple_update_owners(self):
        another_user = User(name='aUser')
        self.db.add(another_user)
        update = Update(
            user=another_user,
            request=UpdateRequest.testing,
            type=UpdateType.enhancement,
            notes='Just another update.',
            date_submitted=datetime(1981, 10, 11),
            requirements='rpmlint',
            stable_karma=3,
            unstable_karma=-3,
            release=Release.query.one()
        )
        self.db.add(update)

        comment = Comment(karma=1, text='Cool! 😃')
        comment.user = another_user
        self.db.add(comment)
        update.comments.append(comment)
        self.db.flush()

        res = self.app.get('/comments/', {"update_owner": "guest,aUser"})
        body = res.json_body
        assert len(body['comments']) == 3

        comment = body['comments'][0]
        assert comment['text'] == 'Cool! 😃'
        comment = body['comments'][1]
        assert comment['text'] == 'srsly.  pretty good.'

    def test_list_comments_by_update_owner_with_none(self):
        user = User(name='ralph')
        self.db.add(user)
        self.db.flush()
        res = self.app.get('/comments/', {"update_owner": "ralph"})
        body = res.json_body
        assert len(body['comments']) == 0
        assert 'errors' not in body

    def test_list_comments_by_nonexistent_update_owner(self):
        res = self.app.get('/comments/', {"update_owner": "santa"}, status=400)
        body = res.json_body
        assert len(body.get('comments', [])) == 0
        assert res.json_body['errors'][0]['name'] == 'update_owner'
        assert res.json_body['errors'][0]['description'] == "Invalid users specified: santa"

    def test_list_comments_with_ignore_user(self):
        res = self.app.get('/comments/', {"ignore_user": "guest"})
        body = res.json_body
        assert len(body['comments']) == 1
        assert'errors' not in body
        comment = body['comments'][0]
        assert comment['text'] == 'srsly.  pretty good.'

    def test_list_comments_with_multiple_ignore_user(self):
        another_user = User(name='aUser')
        self.db.add(another_user)
        update = Update(
            user=another_user,
            request=UpdateRequest.testing,
            type=UpdateType.enhancement,
            notes='Just another update.',
            date_submitted=datetime(1981, 10, 11),
            requirements='rpmlint',
            stable_karma=3,
            unstable_karma=-3,
            release=Release.query.one()
        )
        self.db.add(update)

        comment = Comment(karma=1, text='Cool! 😃')
        comment.user = another_user
        self.db.add(comment)
        update.comments.append(comment)
        self.db.flush()

        res = self.app.get('/comments/', {"ignore_user": "guest,anonymous"})
        body = res.json_body
        assert len(body['comments']) == 1
        assert'errors' not in body
        assert body['comments'][0]['text'] == 'Cool! 😃'

    def test_list_comments_with_nonexistent_ignore_user(self):
        res = self.app.get('/comments/', {"ignore_user": "santa"}, status=400)
        body = res.json_body
        assert len(body.get('comments', [])) == 0
        assert res.json_body['errors'][0]['name'] == 'ignore_user'
        assert res.json_body['errors'][0]['description'] == "Invalid users specified: santa"

    def test_put_json_comment(self):
        """ We only want to POST comments, not PUT. """
        self.app.put_json('/comments/', self.make_comment(), status=405)

    def test_post_json_comment(self):
        with fml_testing.mock_sends(api.Message):
            self.app.post_json('/comments/', self.make_comment(text='awesome'))
        up = self.db.query(Build).filter_by(nvr='bodhi-2.0-1.fc17').one().update
        assert len(up.comments) == 3
        assert up.comments[-1]['text'] == 'awesome'

    def test_new_comment(self):
        comment = self.make_comment('bodhi-2.0-1.fc17', text='superb')
        with fml_testing.mock_sends(api.Message):
            r = self.app.post_json('/comments/', comment)
        comment = r.json_body['comment']
        assert comment['text'] == 'superb'
        assert comment['user']['name'] == 'guest'
        assert comment['author'] == 'guest'
        assert comment['update']['title'] == 'bodhi-2.0-1.fc17'
        assert comment['karma'] == 0

    def test_no_self_karma(self):
        " Make sure you can't give +1 karma to your own updates.. "
        comment = self.make_comment('bodhi-2.0-1.fc17', karma=1)
        # The author of this comment is "guest"

        up = self.db.query(Build).filter_by(nvr='bodhi-2.0-1.fc17').one().update
        assert up.user.name == 'guest'

        with fml_testing.mock_sends(api.Message):
            r = self.app.post_json('/comments/', comment)
        comment = r.json_body['comment']
        assert comment['user']['name'] == 'guest'
        assert comment['update']['title'] == 'bodhi-2.0-1.fc17'
        caveats = r.json_body['caveats']
        assert len(caveats) == 1
        assert caveats[0]['name'] == 'karma'
        assert caveats[0]['description'] == "You may not give karma to your own updates."
        assert comment['karma'] == 0  # This is the real check

    def test_comment_on_locked_update(self):
        """ Make sure you can comment on locked updates. """
        # Lock it
        up = self.db.query(Build).filter_by(nvr=up2).one().update
        up.locked = True
        up.status = UpdateStatus.testing
        up.request = None
        assert len(up.comments) == 0  # Before
        assert up.karma == 0          # Before
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.flush()

        comment = self.make_comment(up2, karma=1)
        with fml_testing.mock_sends(api.Message):
            self.app.post_json('/comments/', comment)

        up = self.db.query(Build).filter_by(nvr=up2).one().update
        assert len(up.comments) == 1  # After
        assert up.karma == 1          # After

    def test_comment_on_locked_update_no_threshhold_action(self):
        " Make sure you can't trigger threshold action on locked updates "
        # Lock it
        up = self.db.query(Build).filter_by(nvr=up2).one().update
        up.locked = True
        up.status = UpdateStatus.testing
        up.request = UpdateStatus.stable
        up.stable_karma = 1
        up.unstable_karma = -1
        assert len(up.comments) == 0  # Before
        assert up.karma == 0          # Before
        # Clear pending messages
        self.db.info['messages'] = []
        self.db.flush()

        comment = self.make_comment(up2, karma=-1)
        with fml_testing.mock_sends(api.Message):
            self.app.post_json('/comments/', comment)

        up = self.db.query(Build).filter_by(nvr=up2).one().update
        assert len(up.comments) == 1  # After
        assert up.karma == -1         # After
        # Ensure that the request did not change .. don't trigger something.
        assert up.status.value == UpdateStatus.testing.value
        assert up.request.value == UpdateRequest.stable.value

    def test_comment_not_loggedin(self):
        """
        Test that 403 error is returned if a non-authenticated 'post comment'
        request is received. It's important that we return 403 here so the
        client will know to re-authenticate
        """
        anonymous_settings = copy.copy(self.app_settings)
        anonymous_settings.update({
            'authtkt.secret': 'whatever',
            'authtkt.secure': True,
        })
        with mock.patch('bodhi.server.Session.remove'):
            app = webtest.TestApp(main({}, session=self.db, **anonymous_settings))

        csrf = app.get('/csrf', headers={'Accept': 'application/json'}).json_body['csrf_token']
        update = Build.query.filter_by(nvr='bodhi-2.0-1.fc17').one().update.alias
        comment = {
            'update': update,
            'text': 'Test',
            'karma': 0,
            'csrf_token': csrf,
        }
        res = app.post_json('/comments/', comment, status=403)
        assert 'errors' in res.json_body
