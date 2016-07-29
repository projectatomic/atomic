require([
    "jquery",
    "base1/cockpit",
], function($, cockpit) {
  var input = $("#new");
  var service = cockpit.dbus("org.atomic");
  var proxy = service.proxy("org.atomic", "/org/atomic/object");
  proxy.wait(function () {
    if (!proxy.valid) {
        $('#ui').hide();
        $('#curtain').show();
    }
    else {
      run_scan_list();
    }
    $('body').show();
  });

  $("#Run").on("click", run_request);
  function run_scan_list() {
    var call = proxy.ScanList();
    call.done(function(result) {
      response = JSON.parse(result);
      for (var i = 0; i < response.length; i++) {
        var radio = document.createElement('input');
        radio.type = "radio";
        radio.setAttribute("name", "scanner");
        radio.setAttribute("value", response[i]["scanner_name"]);
        var label = document.createElement('label')
        label.htmlFor = "id";
        label.appendChild(document.createTextNode(response[i]["scanner_name"]));
        document.body.appendChild(radio);
        document.body.appendChild(label);
        scanned_list = response[i]["scans"];
        for (var j = 0; j < scanned_list.length; j++) {
          var radio_type = document.createElement('input');
          radio_type.type = "radio";
          radio_type.setAttribute("name", "scan_type");
          radio_type.setAttribute("value", scanned_list[j]["name"]);
          label = document.createElement('label')
          label.htmlFor = "id";
          label.appendChild(document.createTextNode(scanned_list[j]["name"]));
          document.body.appendChild(radio_type);
          document.body.appendChild(label);
        }
      }
      run_images();
    });

    call.fail(function(error) {
      console.warn(error);
    });
  }

  function run_request() {
    var scan_targets = [];
    $('input[name="image"]:checked').each(function() {
      scan_targets.push($(this).val());
    });
    if(typeof scan_targets == "undefined") {
      scan_targets = [];
    }
    var scanner = $('input[name="scanner"]:checked').val();
    if(typeof scanner == "undefined") {
      scanner = '';
    }
    var scan_type = $('input[name="scan_type"]:checked').val();
    if(typeof scan_type == "undefined") {
      scan_type = '';
    }
    run_scan(scan_targets, scanner, scan_type)
  }

  function run_scan_async(scan_targets, scanner, scan_type) {
    var call = proxy.ScheduleScan(scan_targets, scanner, scan_type, rootfs, false, false, false);
    call.done(function(result) {
      while(true){
        NewCall = proxy.GetScanResults(result);
        NewCall.done(function(data) {
          if(data.length > 0) {
            console.log(data);
          }
        });
      }
    });

    call.fail(function(error) {
      console.warn(error);
    });
  }

  function run_scan(scan_targets, scanner, scan_type) {
    var call;
    call = proxy.Scan(scan_targets, scanner, scan_type, [], false, false, false)
    call.done(function(result) {
      var label = document.createElement('label')
      label.htmlFor = "id";
      label.appendChild(document.createTextNode(JSON.stringify(result)));
      document.body.appendChild(label);
    });

    call.fail(function(error) {
      console.warn(error);
    });
  }

  function run_vulnerable_info() {
    var call = proxy.VulnerableInfo();
    call.done(function(result) {
      console.log(result);
    });

    call.fail(function(error) {
      console.warn(error);
    });
  }

  function run_update(image) {
    var call = proxy.Update(image);
    call.done(function() {
      console.log("Success");
    });

    call.fail(function(error) {
      console.warn(error);
    });
  }

  function run_images() {
    var call = proxy.Images();
    var text = "Repository            Last Scanned\n";
    call.done(function(result) {
      response = JSON.parse(result);
      for (var i = 2; i < response.length; i++) {
        text += response[i]["repo"] + "            ";
        var checkbox = document.createElement('input');
        checkbox.type = "checkbox";
        checkbox.setAttribute("name", "image");
        checkbox.setAttribute("value", response[i]["repo"]);
        var label = document.createElement('label')
        label.htmlFor = "id";
        label.appendChild(document.createTextNode(response[i]["repo"]));
        document.body.appendChild(checkbox);
        document.body.appendChild(label);
        if ("Time" in response[i]["vuln_info"]) {
          text += response[i]["vuln_info"]["Time"] + " ";
        }

        if(response[i]["vulnerable"]) {
          text += "*\n";
        }

        else {
          text += "\n";
        }
      }
      label = document.createElement('label');
      label.htmlFor = "id";
      label.appendChild(document.createTextNode(text));
      document.body.appendChild(label);
    });

    call.fail(function(error) {
      console.warn(error);
    });
  }
});
