# -*- coding: utf-8 -*-
# Copyright © 2014-2018 Red Hat, Inc. and others.
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.
"""
Fedora-flavored Markdown.

Author: Ralph Bean <rbean@redhat.com>
"""

from markdown.extensions import Extension
import markdown.inlinepatterns
import markdown.postprocessors
import markdown.util
import pyramid.threadlocal


MENTION_RE = r'(?<!\S)(@\w+)'
BUGZILLA_RE = r'([a-zA-Z]+)(#[0-9]{5,})'


def user_url(name):
    """
    Return a URL to the given username.

    Args:
        name (basestring): The username of the user we want a URL for.
    Returns:
        basestring: A URL to the requested user.
    """
    request = pyramid.threadlocal.get_current_request()
    return request.route_url('user', name=name)


def bug_url(tracker, idx):
    """
    Return the URL for the given bug.

    Args:
        tracker (basestring): Which bug tracker is being referenced. May be any of 'fedora',
            'gnome', 'kde', 'mozilla', 'pear', 'perl', 'php', 'python', 'rh', or 'rhbz'.
        idx (basestring or int): The bug number.
    Returns:
        basestring: The URL of the given bug.
    Raises:
        KeyError: If the given tracker is not supported by this function.
    """
    try:
        return {
            'fedora': "https://bugzilla.redhat.com/show_bug.cgi?id=%s",
            'gnome': "https://bugzilla.gnome.org/show_bug.cgi?id=%s",
            'kde': "https://bugs.kde.org/show_bug.cgi?id=%s",
            'mozilla': "https://bugzilla.mozilla.org/show_bug.cgi?id=%s",
            'pear': "http://pear.php.net/bugs/bug.php?id=%s",
            'perl': "https://rt.cpan.org/Public/Bug/Display.html?id=%s",
            'php': "https://bugs.php.net/bug.php?id=%s",
            'python': "https://bugs.python.org/issue%s",
            'rh': "https://bugzilla.redhat.com/show_bug.cgi?id=%s",
            'rhbz': "https://bugzilla.redhat.com/show_bug.cgi?id=%s"}[tracker.lower()] % idx

    except KeyError:
        return None


class MentionPattern(markdown.inlinepatterns.Pattern):
    """Match username mentions and point to their profiles."""

    def handleMatch(self, m):
        """
        Build and return an Element that links to the matched User's profile.

        Args:
            m (re.MatchObject): The regex match on the username.
        Return:
            xml.etree.Element: An html anchor referencing the user's profile.
        """
        el = markdown.util.etree.Element("a")
        name = markdown.util.AtomicString(m.group(2))
        el.set('href', user_url(name[1:]))
        el.text = name
        return el


class BugzillaPattern(markdown.inlinepatterns.Pattern):
    """Match bug tracker patterns."""

    def handleMatch(self, m):
        """
        Build and return an Element that links to the referenced bug.

        Args:
            m (re.MatchObject): The regex match on the bug.
        Returns:
            xml.etree.Element: An html anchor referencing the matched bug.
        """
        tracker = markdown.util.AtomicString(m.group(2))
        idx = markdown.util.AtomicString(m.group(3))
        url = bug_url(tracker, idx[1:])

        if url is None:
            return tracker + idx

        el = markdown.util.etree.Element("a")
        el.set('href', url)
        el.text = idx
        return el


class SurroundProcessor(markdown.postprocessors.Postprocessor):
    """A postprocessor to surround the text with a markdown <div>."""

    def run(self, text):
        """
        Return text wrapped in a <div> with a markdown class.

        Args:
            text (str): The text to wrap in a <div>.
        Returns:
            str: The text wrapped in a <div>.
        """
        return "<div class='markdown'>" + text + "</div>"


class BodhiExtension(Extension):
    """Bodhi's markdown Extension."""

    def extendMarkdown(self, md, md_globals):
        """
        Extend markdown to add our patterns and postprocessor.

        Args:
            md (Markdown): An instance of the Markdown class.
            md_globals (dict): Contains all the various global variables within the markdown module.
        """
        md.inlinePatterns.add('mention', MentionPattern(MENTION_RE, md), '_end')
        md.inlinePatterns.add('bugzilla', BugzillaPattern(BUGZILLA_RE, md), '_end')
        md.postprocessors.add('surrond', SurroundProcessor(md), '_end')
