import os
import getpass

from fedora.client import BodhiClient

build = u'qt-creator-3.4.1-3.fc23'
username = os.getenv('USER')
#username = raw_input('FAS Username: ')
#password = getpass.getpass()
import subprocess
p = subprocess.Popen(['/usr/bin/pass', 'fedora'], stdout=subprocess.PIPE)
out, err = p.communicate()
password = out.strip()

print('Logging into bodhi2')
bodhi = BodhiClient(staging=True, username=username, password=password)

print('Logged in! Creating new update...')

result = bodhi.save(
        builds=build,
        type='bugfix',
        notes='The quick brown fox jumped over the lazy dog',
)
#assert result.status_code == 200
print(result.text)

print('Querying update')
result = bodhi.query(builds='qt-creator-3.4.1-3.fc23')
assert result.status_code == 200
json = result.json()
updates = json['updates']
update = updates[0]
assert len(updates) == 1, len(updates)
assert json['total'] == 1, json
alias = update['alias']
print(alias)

print(bodhi.update_str(update))
print('')
print(bodhi.update_str(update, minimal=True))

print('Call /latest_builds')
result = bodhi.latest_builds('kernel')
assert result.status_code == 200
print(result.json())
#
print('Querying all releases')
result = bodhi.get_releases()
print(result)
#print(result.json())

print('Looking for candidate builds')
print(bodhi.candidates())

for update in bodhi.testable():
    print(bodhi.update_str(update))

print('Querying by release')
result = bodhi.query(release='f23')
assert result.status_code == 200
updates = json['updates']
assert len(updates) == 1, len(updates)
assert json['total'] == 1, json
assert updates[0]['alias'] == alias
print('%d updates returned' % len(updates))

print('Querying by release and package')
result = bodhi.query(package='qt-creator', release='f23')
assert result.status_code == 200
updates = json['updates']
assert len(updates) == 1, len(updates)
assert json['total'] == 1, json
assert updates[0]['alias'] == alias
print('%d updates returned' % len(updates))

print('Querying by release and package and status')
result = bodhi.query(package='qt-creator', release='f23', status='pending')
assert result.status_code == 200
updates = json['updates']
assert len(updates) == 1, len(updates)
assert json['total'] == 1, json
assert updates[0]['alias'] == alias
print('%d updates returned' % len(updates))

print('Querying by release and package and status and limit')
result = bodhi.query(type='security', limit=2)
assert result.status_code == 200
json = result.json()
updates = json['updates']
assert len(updates) == 2, len(updates)
assert updates[0]['type'] == 'security'
print('%d updates returned' % len(updates))

print('Querying by release with (blockerbugs)')
result = bodhi.query(limit=100, release='f23')
print(result.text)
json = result.json()
updates = json['updates']
assert len(updates) == 2, len(updates)
assert updates[0]['type'] == 'security'
print('%d updates returned' % len(updates))

print('Requesting stable')
result = bodhi.request(update=alias, request='stable')
json = result.json()
assert json['status'] == 'error'
assert len(json['errors']) == 1
assert json['errors'][0]['name'] == 'request'

print('Requesting testing')
result = bodhi.request(update=alias, request='testing')
assert result.status_code == 200
json = result.json()
assert json['update']['request'] == 'testing'

print('Revoking request')
result = bodhi.request(update=alias, request='revoke')
assert result.status_code == 200
print(result.text)
json = result.json()
assert json['update']['request'] == None

print('Adding comment')
result = bodhi.comment(update=alias, comment='yay', karma=1)
assert result.status_code == 200
json = result.json()
comment = json['comment']
assert comment['author'] == username
assert comment['text'] == u'yay'
assert comment['update']['title'] == build
