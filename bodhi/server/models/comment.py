# Copyright © 2011-2019 Red Hat, Inc. and others.
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
"""Bodhi's comment models."""

from datetime import datetime
import typing

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UnicodeText
from sqlalchemy.orm import relationship

from bodhi.server.models import Base

if typing.TYPE_CHECKING:  # pragma: no cover
    import pyramid  # noqa: 401


# Used for many-to-many relationships between karma and a bug
class BugKarma(Base):
    """
    Karma for a bug associated with a comment.

    Attributes:
        karma (int): The karma associated with this bug and comment.
        comment (Comment): The comment this BugKarma is part of.
        bug (Bug): The bug this BugKarma pertains to.
    """

    __tablename__ = 'comment_bug_assoc'

    karma = Column(Integer, default=0)

    comment_id = Column(Integer, ForeignKey('comments.id'))
    comment = relationship("Comment", backref='bug_feedback')

    bug_id = Column(Integer, ForeignKey('bugs.bug_id'))
    bug = relationship("Bug", backref='feedback')


# Used for many-to-many relationships between karma and a TestCase
class TestCaseKarma(Base):
    """
    Karma for a TestCase associated with a comment.

    Attributes:
        karma (int): The karma associated with this TestCase comment.
        comment (Comment): The comment this TestCaseKarma is associated with.
        testcase (TestCase): The TestCase this TestCaseKarma pertains to.
    """

    __tablename__ = 'comment_testcase_assoc'

    karma = Column(Integer, default=0)

    comment_id = Column(Integer, ForeignKey('comments.id'))
    comment = relationship("Comment", backref='testcase_feedback')

    testcase_id = Column(Integer, ForeignKey('testcases.id'))
    testcase = relationship("TestCase", backref='feedback')


class Comment(Base):
    """
    An update comment.

    Attributes:
        karma (int): The karma associated with this comment. Defaults to 0.
        karma_critpath (int): The critpath karma associated with this comment. Defaults to 0.
            **DEPRECATED** no longer used in the UI
        text (str): The text of the comment.
        timestamp (datetime.datetime): The time the comment was created. Defaults to
            the return value of datetime.utcnow().
        update (Update): The update that this comment pertains to.
        user (User): The user who wrote this comment.
    """

    __tablename__ = 'comments'
    __exclude_columns__ = tuple()
    __get_by__ = ('id',)

    karma = Column(Integer, default=0)
    karma_critpath = Column(Integer, default=0)
    text = Column(UnicodeText, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    update_id = Column(Integer, ForeignKey('updates.id'), index=True)
    user_id = Column(Integer, ForeignKey('users.id'))

    def url(self) -> str:
        """
        Return a URL to this comment.

        Returns:
            A URL to this comment.
        """
        url = self.update.get_url() + '#comment-' + str(self.id)
        return url

    @property
    def unique_testcase_feedback(self) -> typing.List[TestCaseKarma]:
        """
        Return a list of unique :class:`TestCaseKarma` objects found in the testcase_feedback.

        This will filter out duplicates for :class:`TestCases <TestCase>`. It will return the
        correct number of TestCases in testcase_feedback as a list.

        Returns:
            A list of unique :class:`TestCaseKarma` objects associated with this comment.
        """
        feedbacks = self.testcase_feedback
        unique_feedbacks = set()
        filtered_feedbacks = list()
        for feedback in feedbacks:
            if feedback.testcase.name not in unique_feedbacks:
                unique_feedbacks.add(feedback.testcase.name)
                filtered_feedbacks.append(feedback)

        return filtered_feedbacks

    @property
    def rss_title(self) -> str:
        """
        Return a formatted title for the comment using update alias and comment id.

        Returns:
            A string representation of the comment for RSS feed.
        """
        return "{} comment #{}".format(self.update.alias, self.id)

    def __json__(self, *args, **kwargs) -> dict:
        """
        Return a JSON string representation of this comment.

        Args:
            args: A list of extra args to pass on to :meth:`BodhiBase.__json__`.
            kwargs: Extra kwargs to pass on to :meth:`BodhiBase.__json__`.
        Returns:
            A JSON-serializable dict representation of this comment.
        """
        result = super(Comment, self).__json__(*args, **kwargs)
        # Duplicate 'user' as 'author' just for backwards compat with bodhi1.
        # Things like the message schemas and fedbadges rely on this.
        if result['user']:
            result['author'] = result['user']['name']

        # Similarly, duplicate the update's alias as update_alias.
        result['update_alias'] = result['update']['alias']

        # Updates used to have a karma column which would be included in result['update']. The
        # column was replaced with a property, so we need to include it here for backwards
        # compatibility.
        result['update']['karma'] = self.update.karma

        return result

    def __str__(self) -> str:
        """
        Return a str representation of this comment.

        Returns:
            A str representation of this comment.
        """
        karma = '0'
        if self.karma != 0:
            karma = '%+d' % (self.karma,)
        return "%s - %s (karma: %s)\n%s" % (self.user.name, self.timestamp, karma, self.text)
