from faker import Faker

import python_freeipa

USER_PASSWORD = "password"

fake = Faker()
fake.seed_instance(0)

ipa = python_freeipa.ClientLegacy(
    host="ipa.tinystage.test", verify_ssl="/etc/ipa/ca.crt"
)
ipa.login("admin", "password")

for group in ["packager", "provenpackager"]:
    if ipa.group_find(cn=group).get('result') != []:
        print(f"group {group} is already in tinystage")
        continue
    ipa.group_add(group, f"A group for {group}", fasgroup=True)
    ipa._request("fasagreement_add_group", "FPCA", {"group": group})

for username in ["tinystage_packager", "tinystage_provenpackager", "{{ fas_username }}"]:
    if username == "":
        continue
    if ipa.user_find(uid=username).get('result') != []:
        print(f"user {username} is already in tinystage")
        continue
    firstName = fake.first_name()
    lastName = fake.last_name()
    fullname = firstName + " " + lastName
    print(f"adding user {username} - {fullname}")
    try:
        ipa.user_add(
            username,
            firstName,
            lastName,
            fullname,
            disabled=False,
            user_password=USER_PASSWORD,
            fasircnick=[username, username + "_"],
            faslocale="en-US",
            fastimezone="Australia/Brisbane",
            fasstatusnote="active",
            fasgpgkeyid=[],
        )
        ipa._request("fasagreement_add_user", "FPCA", {"user": username})
        ipa.group_add_member("packager", username)
        if username == "tinystage_provenpackager":
            ipa.group_add_member("provenpackager", username)
    except python_freeipa.exceptions.FreeIPAError as e:
        print(e)
