<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<html xmlns="http://www.w3.org/1999/xhtml" xmlns:py="http://purl.org/kid/ns#"
    py:extends="'master.kid'">

<head>
    <meta content="text/html; charset=UTF-8" http-equiv="content-type" py:replace="''"/>
    <script language="javascript" type="text/javascript" src="${tg.url('/static/js/jquery.flot.js')}"></script>
</head>
<body>
    <center>
        <h2>Fedora 7 Updates</h2>
        <div id="all" style="width:600px;height:300px;"></div>
        <script id="source" language="javascript" type="text/javascript">
        $.getJSON("/updates/metrics/all",
            function(data){
                bugs = data['timeline']['bugfix'];
                enhancements = data['timeline']['enhancement'];
                security = data['timeline']['security'];
                all = data['all']
                $.plot($("#all"), [
                    {
                        data  : all,
                        label : "All Updates",
                        bars  : { show : true }
                    },
                    {
                        data   : enhancements,
                        label  : "Enhancement",
                        lines  : { show : true },
                        points : { show : true }
                    },
                    {
                        data   : security,
                        label  : "Security",
                        lines  : { show : true },
                        points : { show : true }
                    },
                    {
                        data   : bugs,
                        label  : "Bugfix",
                        lines  : { show : true },
                        points : { show : true }
                    }],
                    {
                        grid  : { backgroundColor: "#fffaff" },
                        xaxis : { ticks : data['months'] },
                        yaxis : { max : 850 },
                    }
                );
        });
        </script>

 
        <h2>Security updates per month</h2>
        <div id="security" style="width:600px;height:300px;"></div>
        <script id="source" language="javascript" type="text/javascript">
        $(function () {
            $.getJSON("/updates/metrics/security",
                function(data){
                    f7 = data['timeline']['F7'];
                    f8 = data['timeline']['F8'];
                    $.plot($("#security"), [
                        {
                            data  : f7, label : "Fedora 7",
                            lines : { show : true }
                        },
                        //{
                        //    data  : f8, label : "Fedora 8",
                        //    lines : { show : true }
                        //}
                        ],
                        {
                            grid  : { backgroundColor: "#fffaff" },
                            xaxis : { ticks : data['months'] },
                        }
                    );
            });
        });
        </script>

        <h2>Most updates per package</h2>
        <div id="most_updated" style="width:600px;height:300px;"></div>
        <script id="source" language="javascript" type="text/javascript">
        $.getJSON("/updates/metrics/most_updated",
                function(data){
                    pkgs = data['packages'];
                    $.plot($("#most_updated"), [
                        // Hack to get the color we want :)
                        { data : [[0,0]] }, { data : [[0,0]] },
                        { data : [[0,0]] }, { data : [[0,0]] },
                        { data : [[0,0]] }, { data : [[0,0]] },
                        {
                            data : pkgs,
                            bars : { show : true }
                        }],
                        {
                            grid  : { backgroundColor: "#fffaff" },
                            xaxis : { ticks : data['pkgs'] },
                        }
                    );
            });
        </script>

        <h2>Most updates per developer</h2>
        <div id="active_devs" style="width:600px;height:300px;"></div>
        <script id="source" language="javascript" type="text/javascript">
        $.getJSON("/updates/metrics/active_devs",
                function(data){
                    $.plot($("#active_devs"), [
                        { data : [[0,0]] }, { data : [[0,0]] }, { data : [[0,0]] },
                        {
                            data : data['data'],
                            bars : { show : true }
                        }],
                        {
                            grid  : { backgroundColor: "#fffaff" },
                            xaxis : { ticks : data['people'] },
                        }
                    );
            });
        </script>

    </center>
</body>
</html>
