import tw2.core
import tw2.forms
import tw2.sqla
import tw2.dynforms
import tw2.jqplugins.jqgrid

import bodhi.models


class UpdateList(tw2.sqla.DbListPage):
    entity = bodhi.models.Update
    title = 'Updates'
    newlink = tw2.forms.LinkField(link='/new', text='New', value=1)
    class child(tw2.forms.GridLayout):
        title = tw2.forms.LabelField()
        id = tw2.forms.LinkField(link='/edit?id=$', text='Edit', label=None)


class NewUpdateForm(tw2.sqla.DbFormPage):
    entity = bodhi.models.Update
    redirect = '/updates'
    title = 'Submit a new update'

    class child(tw2.dynforms.CustomisedTableForm):
        action = '/save'
        id = tw2.forms.HiddenField()

        class builds(tw2.dynforms.GrowingGridLayout):
            # TODO: package auto-completion
            package = tw2.forms.TextField()
            # auto-populate this with the latest-pkg candidate tag
            version = tw2.forms.TextField()

        type_ = tw2.forms.SingleSelectField(
                options=bodhi.models.UpdateType.values(),
                validator=tw2.core.OneOfValidator(
                    values=bodhi.models.UpdateType.values()))
        notes = tw2.forms.TextArea(rows=5, cols=50,
                validator=tw2.core.StringLengthValidator(min=10))

        class bugs(tw2.forms.TableFieldSet):
            bugs = tw2.forms.TextField()
            closebugs = tw2.forms.CheckBox(label='Automatically close bugs',
                    validator=tw2.core.BoolValidator())

        class karma(tw2.forms.TableFieldSet):
            autokarma = tw2.forms.CheckBox(label='Enable karma automatism',
                    validator=tw2.core.BoolValidator())
            stablekarma = tw2.forms.TextField(label='Stable threshold', size=2,
                    value=3, validator=tw2.core.IntValidator())
            unstablekarma = tw2.forms.TextField(label='Unstable threshold', size=2,
                    value=-3, validator=tw2.core.IntValidator())

        reboot = tw2.forms.CheckBox(label='Suggest reboot',
                validator=tw2.core.BoolValidator())
