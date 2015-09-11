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

""" Fedora-flavored Markdown

Author: Ralph Bean <rbean@redhat.com>
"""

import markdown.inlinepatterns
import markdown.postprocessors
import markdown.util
import pyramid.threadlocal


def user_url(name):
    request = pyramid.threadlocal.get_current_request()
    return request.route_url('user', name=name)


def bugzilla_url(idx):
    return "https://bugzilla.redhat.com/show_bug.cgi?id=%s" % idx


def inject():
    """ Hack out python-markdown to do the autolinking that we want. """

    # First, make it so that bare links get automatically linkified.
    markdown.inlinepatterns.AUTOLINK_RE = '(%s)' % '|'.join([
        r'<(?:f|ht)tps?://[^>]*>',
        r'\b(?:f|ht)tps?://[^)<>\s]+[^.,)<>\s]',
        r'\bwww\.[^)<>\s]+[^.,)<>\s]',
        r'[^(<\s]+\.(?:com|net|org)\b',
    ])

    # Second, build some Pattern objects for @mentions, #bugs, etc...
    class MentionPattern(markdown.inlinepatterns.Pattern):
        def handleMatch(self, m):
            el = markdown.util.etree.Element("a")
            name = markdown.util.AtomicString(m.group(2))
            el.set('href', user_url(name[1:]))
            el.text = name
            return el

    class BugzillaPattern(markdown.inlinepatterns.Pattern):
        def handleMatch(self, m):
            el = markdown.util.etree.Element("a")
            idx = markdown.util.AtomicString(m.group(2))
            el.set('href', bugzilla_url(idx[1:]))
            el.text = idx
            return el

    MENTION_RE = r'(@\w+)'
    BUGZILLA_RE = r'(#[0-9]{6,})'

    class SurroundProcessor(markdown.postprocessors.Postprocessor):
        def run(self, text):
            return "<div class='markdown'>" + text + "</div>"

    # Lastly, monkey-patch the build_inlinepatterns func to insert our patterns
    original_pattern_builder = markdown.build_inlinepatterns

    def extended_pattern_builder(md_instance, **kwargs):
        patterns = original_pattern_builder(md_instance, **kwargs)
        patterns['mention'] = MentionPattern(MENTION_RE, md_instance)
        patterns['bugzillas'] = BugzillaPattern(BUGZILLA_RE, md_instance)
        return patterns

    markdown.build_inlinepatterns = extended_pattern_builder

    original_postprocessor_builder = markdown.build_postprocessors

    def extended_postprocessor_builder(md_instance, **kwargs):
        processors = original_postprocessor_builder(md_instance, **kwargs)
        processors['surround'] = SurroundProcessor(md_instance)
        return processors

    markdown.build_postprocessors = extended_postprocessor_builder
