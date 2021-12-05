#!/usr/bin/env python3
# Copyright 2021 Erik Lönroth
# See LICENSE file for licensing details.

import logging
import os
import shutil


from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, WaitingStatus, MaintenanceStatus
import subprocess as sp
import sys

import utils

logger = logging.getLogger(__name__)

EMOJI_CORE_HOOK_EVENT = "\U0001F4CC"
EMOJI_MESSAGE = "\U0001F4AC"
EMOJI_GREEN_DOT = "\U0001F7E2"
EMOJI_RED_DOT = "\U0001F534"
EMOJI_PACKAGE = "\U0001F4E6"


class IPFSClusterCharm(CharmBase):
    """Charm the hello service with all core hooks."""

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.leader_elected, self._on_leader_elected)
        self.framework.observe(self.on.leader_settings_changed, self._on_leader_settings_changed)
        self.framework.observe(self.on.stop, self._on_stop)
        self.framework.observe(self.on.remove, self._on_remove)
        self.framework.observe(self.on.stop, self._on_stop)
        self.framework.observe(self.on.update_status, self._on_update_status)
        self.framework.observe(self.on.collect_metrics, self._on_collect_metrics)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)
        # peer
        self.framework.observe(self.on.peer_relation_joined, self._on_peer_relation_joined)
        self.framework.observe(self.on.peer_relation_departed, self._on_peer_relation_departed)
        self.framework.observe(self.on.peer_relation_changed, self._on_peer_relation_changed)


        self._stored.set_default(sources_uri=self.config["sources-uri"],
                                 restart_on_reconfig=self.config["restart-on-reconfig"])


    def _on_install(self, event):
        """
        Install your software here plus any dependencies, utilities and everything you need to run
        your service over time.

        Optionally take care of installing resources attached with the charm deployment.

        In this charm, we install a package and a service unit file which will use hello.

        This hook is ran after the storage-filesystem-attached hook - only once in the entire lifetime of the unit.
        """
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)

        logger.info(f"Installing from snap ipfs {EMOJI_PACKAGE}")
        # os.system(f"snap install ipfs --channel={self._stored.snap_channel}")
        utils.fetch_and_extract_sources(self._stored.sources_uri)
        
        # Install unit file for hello (one-shot service)
        shutil.copyfile('templates/etc/systemd/system/ipfs-cluster.service', '/etc/systemd/system/ipfs-cluster.service')

        # (re)config hello.
        self._reconfig_ipfs(restart=False)


    def _on_config_changed(self, event):
        """
        Deal with charm configuration changes here.

        Detect changes to individual config items, by storing and comparing values in self._stored

        This hook is run after the start hook.
        This hook run after the upgrade-charm hook.
        This hook is run after the leader-elected hook.
        """
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)

        if self.config["sources-uri"] != self._stored.sources_uri:
            self._stored.sources_uri = self.config["sources-uri"]
            self._reconfig_ipfs_cluster(restart=self.config["restart-on-reconfig"])

        self._on_update_status(event)

    def _on_start(self, event):
        """
            Start your service here, possibly defer (wait) until conditions are OK.
        """
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)
        logger.info(f"{EMOJI_GREEN_DOT} Starting the ipfs-daemon service...")
        os.system('systemctl start ipfs-daemon.service')

        # Calling update_status gives quick feedback when deploying starts up.
        self._on_update_status(event)

    def _on_leader_elected(self, event):
        """
            This is only run on the unit which is selected by juju as leader.
            We are not implementing anything here. See the "leadership" charm for an example.
        """
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)

    def _on_leader_settings_changed(self, event):
        """
            This is only run on the unit which is selected by juju as leader.
            We are not implementing anything here. See the "leadership" charm for an example.
        """
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)

    def _on_update_status(self, event):
        """
            This runs every 5 minutes.

            Have one place to figure out status for the charm is a good strategy for a beginner charmer.
        """
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)

        if not os.system('systemctl is-active ipfs-daemon.service') == 0:
            logger.info("ipfs-daemon service is not running.")
            self.unit.status = MaintenanceStatus("Inactive.")
        else:
            logger.info(f"ipfs-daemon service is running.")
            self.unit.status = ActiveStatus("Running.")

    def _on_upgrade_charm(self, event):
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)

    def _on_stop(self, event):
        """
        Bring down your service, possibly defer until all systems are good to go similar to start hook.
        """
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)

        logger.info(f"{EMOJI_RED_DOT} Stopping the ipfs-daemon service...")
#        os.system('systemctl stop ipfs-daemon.service')


    def _on_remove(self, event):
        """
        Remove stuff you might want to clean up.

        This hook is run after the stop hook.
        """
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)

        logger.info(f"Removing ipfs {EMOJI_PACKAGE}")
#        os.system('snap remove ipfs')


    def _on_collect_metrics(self, event):
        """
        This runs every 5 minutes - if metrics are defined in metrics.yaml.

        We don't implement any metrics this in this charm. See the metrics charm for a working example.
        """
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)


    def _on_peer_relation_joined(self, event):
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)
        pass

    def _on_peer_relation_departed(self, event):
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)
        pass

    def _on_peer_relation_changed(self, event):
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)
        pass

    def _reconfig_ipfs_cluster(self, restart=False):
        """
        Reconfigures the startup parameters of hello.service by modifying the /etc/default/hello file.
        Reloads systemd daemons.

        Optionally, restart the service.
        """
        logger.info(f"{EMOJI_MESSAGE} Configuring ipfs-daemon snap-channel: {self._stored.snap_channel}")
#        self._stored.snap_channel = self.config["snap-channel"]
#        os.system(f"snap refresh ipfs --channel={self._stored.snap_channel}")

        with open('/etc/default/ipfs-cluster', 'w') as f:
            f.write(f"CUSTOM_ARGS=\\'cluster\\'")
        os.system('systemctl daemon-reload')

        if restart:
            logger.info(f"{EMOJI_GREEN_DOT} Restarting hello.")
#            os.system('systemctl restart ipfs-daemon.service')

if __name__ == "__main__":
    main(IPFSClusterCharm)
