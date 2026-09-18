$(function () {
    function AutoFarmViewModel(parameters) {
        var self = this;
        self.settings = parameters[0];
        self.loginState = parameters[1];

        self.notification = ko.observable(null);
        self.newQueuePath = ko.observable("");
        self.bedClearResult = ko.observable(null);

        self.queue = ko.computed(function () {
            var plugin = self.settings.settings.plugins.autofarm;
            return plugin ? plugin.queue() : [];
        });

        // Fetched from our own status endpoint rather than read out of
        // settingsViewModel's webcam tree - that structure has moved around
        // between OctoPrint versions (webcams became plugin-provided in
        // 1.9), whereas our own API resolves it server-side the same way
        // core does and stays correct regardless.
        self.streamUrl = ko.observable("");

        self.refreshStatus = function () {
            OctoPrint.simpleApiGet("autofarm").done(function (status) {
                self.streamUrl(status.stream_url || "");
            });
        };

        self.onStartupComplete = self.refreshStatus;
        self.onTabChange = self.refreshStatus;
        // Belt-and-suspenders: fetch immediately on construction too, so
        // this doesn't depend on onStartupComplete/onTabChange firing at
        // a time OctoPrint.simpleApiGet is actually usable yet.
        self.refreshStatus();

        // custom_bindings means every data-bind in our templates resolves
        // against THIS viewmodel, not the raw settingsViewModel tree - so
        // every settings field the templates reference needs a matching
        // read/write property here, or it silently binds to nothing.
        function settingField(name) {
            return ko.pureComputed({
                read: function () {
                    return self.settings.settings.plugins.autofarm[name]();
                },
                write: function (v) {
                    self.settings.settings.plugins.autofarm[name](v);
                },
            });
        }

        self.enabled = settingField("enabled");
        self.auto_eject = settingField("auto_eject");
        self.printer_profile = settingField("printer_profile");
        self.bed_clear_check = settingField("bed_clear_check");
        self.relay_mode = settingField("relay_mode");
        self.relay_gpio_pin = settingField("relay_gpio_pin");
        self.relay_active_low = settingField("relay_active_low");

        self.addToQueue = function () {
            var path = self.newQueuePath();
            if (!path) return;
            OctoPrint.simpleApiCommand("autofarm", "add_to_queue", {path: path}).done(function () {
                self.newQueuePath("");
                self.settings.requestData();
            });
        };

        self.removeFromQueue = function (index) {
            OctoPrint.simpleApiCommand("autofarm", "remove_from_queue", {index: index}).done(function () {
                self.settings.requestData();
            });
        };

        self.startNext = function () {
            OctoPrint.simpleApiCommand("autofarm", "start_next").done(function () {
                self.notification(null);
            });
        };

        self.setEmptyReference = function () {
            OctoPrint.simpleApiCommand("autofarm", "set_empty_reference");
        };

        self.testEject = function () {
            OctoPrint.simpleApiCommand("autofarm", "test_eject");
        };

        self.testBedClear = function () {
            OctoPrint.simpleApiCommand("autofarm", "check_bed_clear").done(function (result) {
                self.bedClearResult(result);
            });
        };

        self.onDataUpdaterPluginMessage = function (plugin, data) {
            if (plugin !== "autofarm") return;
            self.notification(data);
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: AutoFarmViewModel,
        dependencies: ["settingsViewModel", "loginStateViewModel"],
        elements: ["#settings_plugin_autofarm", "#autofarm_tab"],
    });
});
