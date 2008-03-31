<div xmlns:py="http://purl.org/kid/ns#">
  <script type="text/javascript" src="${tg.url('/static/js/jquery.tablesorter.js')}"></script>
  <table id="${name}" class="tablesorter" cellpadding="0" cellspacing="1" border="0">
    <thead py:if="columns">
      <tr>
        <th py:for="i, col in enumerate(columns)" class="col_${i}">
          ${col.title}
        </th>
      </tr>
    </thead>
    <tbody>
      <tr py:for="i, row in enumerate(value)" class="${i%2 and 'odd' or 'even'}">
        <td py:for="col in columns">
          ${col.get_field(row)}
        </td>
      </tr>
    </tbody>
  </table>
  <a id="append" href="#">More!</a>
  <script>
    $(document).ready(function() { 
      $("#${name}").tablesorter();
        $("#append").click(function() {
         $.get("/updates/foo", function(html) {
            $("#${name} tbody").append(html);
            $("#${name}").trigger("update");
            var sorting = [[2,1],[0,0]];
            $("#${name}").trigger("sorton",[sorting]);
          }); 
          return false; 
        });
    });
  </script>
</div>
