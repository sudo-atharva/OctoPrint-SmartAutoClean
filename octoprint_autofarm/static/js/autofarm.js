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

        self.enabled = ko.pureComputed({
            read: function () {
                return self.settings.settings.plugins.autofarm.enabled();
            },
            write: function (v) {
                self.settings.settings.plugins.autofarm.enabled(v);
            },
        });

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
