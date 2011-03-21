def view_root(context, request):
    return {'items':list(context), 'project':'bodhi'}

def view_model(context, request):
    return {'item':context, 'project':'bodhi'}
