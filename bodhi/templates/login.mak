<h1>OpenID Login</h1>
<% flash = '. '.join(request.session.pop_flash()) %>
<div class="flash">${flash}</div>
<form method="POST" action="${url}">
<input type="text" value="https://admin.fedoraproject.org/accounts/openid/id/" name="openid" size=40 />
  <input type="submit" value="Login" />
</form>
