<% flash = '. '.join(request.session.pop_flash()) %>
<div class="flash">${flash}</div>

${widget.display() | n}
