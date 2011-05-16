<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <meta http-equiv="content-type" content="text/html; charset=utf-8" />
    <title></title>
</head>
  <body>
      <table class="stylized">
          ${page.pager('$link_previous ~3~ $link_next (Page $page of $page_count)')}
          <caption>${caption}</caption>
          <col class="c1" />
          ${grid}
      </table>
  </body>
</html>
