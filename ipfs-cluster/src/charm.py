#!/usr/bin/env python3
# Copyright 2021 Erik Lönroth
# See LICENSE file for licensing details.

import logging
import os
import shutil
from pathlib import Path
import requests
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, WaitingStatus, MaintenanceStatus
import subprocess
import sys
import jinja2

import utils

logger = logging.getLogger(__name__)

EMOJI_CORE_HOOK_EVENT = "\U0001F4CC"
EMOJI_MESSAGE = "\U0001F4AC"
EMOJI_GREEN_DOT = "\U0001F7E2"
EMOJI_RED_DOT = "\U0001F534"
EMOJI_PACKAGE = "\U0001F4E6"

IPFS_HOME = Path('/opt/ipfs/')
IPFS_CTL = Path('/opt/ipfs/ipfs-cluster-ctl/')
IPFS_SERVICE = Path('/opt/ipfs/ipfs-cluster-service/')
IPFS = Path('/opt/ipfs/go-ipfs/')

class IPFSClusterCharm(CharmBase):
    """IPFS cluster with all core hooks."""

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
        self.framework.observe(self.on.cluster_relation_joined, self._on_cluster_relation_joined)
        self.framework.observe(self.on.cluster_relation_departed, self._on_cluster_relation_departed)
        self.framework.observe(self.on.cluster_relation_changed, self._on_cluster_relation_changed)


        self._stored.set_default(service_sources_uri=self.config["service-sources-uri"],
                                 ctl_sources_uri=self.config["ctl-sources-uri"],
                                 restart_on_reconfig=self.config["restart-on-reconfig"])


    def _on_install(self, event):
        """
        Install ipfs-cluster
        """
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)

        logger.info(f"Installing ctl from source uri {EMOJI_PACKAGE}")
        os.system(f"mkdir -p {IPFS_HOME}")
        utils.fetch_and_extract_sources(self._stored.ctl_sources_uri, IPFS_HOME)

        logger.info(f"Installing service from source uri {EMOJI_PACKAGE}")     
        utils.fetch_and_extract_sources(self._stored.service_sources_uri, IPFS_HOME)
        
        shutil.copyfile('templates/etc/systemd/system/ipfs-cluster.service', '/etc/systemd/system/ipfs-cluster.service')
        
        # (re)config
        self._reconfig_ipfs_cluster(restart=False)


    def _on_config_changed(self, event):
        """
        Deal with charm configuration changes here.

        Detect changes to individual config items, by storing and comparing values in self._stored

        This hook is run after the start hook.
        This hook run after the upgrade-charm hook.
        This hook is run after the leader-elected hook.
        """
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)

        if self.config["ctl-sources-uri"] != self._stored.ctl_sources_uri:
            self._stored.ctl_sources_uri = self.config["ctl-sources-uri"]
            self._reconfig_ipfs_cluster(restart=self.config["restart-on-reconfig"])

        if self.config["service-sources-uri"] != self._stored.service_sources_uri:
            self._stored.service_sources_uri = self.config["service-sources-uri"]
            self._reconfig_ipfs_cluster(restart=self.config["restart-on-reconfig"])
            
        self._on_update_status(event)

    def _on_start(self, event):
        """
            Start your service here, possibly defer (wait) until conditions are OK.
        """
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)
        logger.info(f"{EMOJI_GREEN_DOT} Starting ipfs-cluster.service")
        os.system('systemctl start ipfs-cluster.service')

        # Calling update_status gives quick feedback when deploying starts up.
        self._on_update_status(event)
        self.unit.set_workload_version(utils.getIpfsClusterVersion())


    def _on_leader_elected(self, event):
        """
            This is only run on the unit which is selected by juju as leader.
        """
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)
        os.system('sudo -u ubuntu /opt/ipfs/ipfs-cluster-service/ipfs-cluster-service init --force')
        
    def _on_leader_settings_changed(self, event):
        """
            This is only run on the unit which is selected by juju as leader.
        """
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)

    def _on_update_status(self, event):
        """
            This runs every 5 minutes.

            Have one place to figure out status for the charm is a good strategy for a beginner charmer.
        """
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)

        if not os.system('systemctl is-active ipfs-cluster.service') == 0:
            logger.info("ipfs-cluster service is not running.")
            self.unit.status = MaintenanceStatus("Inactive.")
        else:
            logger.info(f"ipfs-daemon service is running.")
            self.unit.status = ActiveStatus("Running.")

        if self.model.unit.is_leader():
                self.unit.set_workload_version(utils.getIpfsClusterVersion())

            
    def _on_upgrade_charm(self, event):
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)

        shutil.copyfile('templates/etc/systemd/system/ipfs-cluster.service', '/etc/systemd/system/ipfs-cluster.service')
        
    def _on_stop(self, event):
        """
        Bring down your service, possibly defer until all systems are good to go similar to start hook.
        """
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)

        logger.info(f"{EMOJI_RED_DOT} Stopping the ipfs-cluster service...")
        os.system('systemctl stop ipfs-cluster.service')


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


    def _on_cluster_relation_joined(self, event):
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)
        pass

    def _on_cluster_relation_departed(self, event):
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)
        pass

    def _on_cluster_relation_changed(self, event):
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)
        pass

    def _ipfs_init(self):
        """
        ./ipfs-cluster-service init
        2021-12-05T16:16:47.604Z	INFO	config	config/config.go:481	Saving configuration
        configuration written to /home/ubuntu/.ipfs-cluster/service.json.
        2021-12-05T16:16:47.607Z	INFO	config	config/identity.go:73	Saving identity
        new identity written to /home/ubuntu/.ipfs-cluster/identity.json
        new empty peerstore written to /home/ubuntu/.ipfs-cluster/peerstore.
        """
        os.chdir(f"{IPFS_SERVICE}")
        os.system('./ipfs-cluster-service init')
        
    def _reconfig_ipfs_cluster(self, restart=False):
        """
        Reconfigures the startup parameters of hello.service by modifying the /etc/default/ipfs-cluster file.
        Reloads systemd daemons.

        Optionally, restart the service.
        """
        logger.info(f"{EMOJI_MESSAGE} Re-Configuring")
        
        template = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                os.path.join(self.charm_dir, 'templates/etc/default/'))).get_template('ipfs-cluster.j2') 
        target = Path('/etc/default/ipfs-cluster')
        ctx = {'peername': 'peeeeeername',
               'secret': 'seeeeecret',
               'cluster_id': 'cluster_iiiiiiid'}
        target.write_text(template.render(ctx))
        
        os.system('systemctl daemon-reload')

        if restart:
            logger.info(f"{EMOJI_GREEN_DOT} Restarting ipfs-cluster.")
            os.system('systemctl restart ipfs-cluster.service')

            
if __name__ == "__main__":
    main(IPFSClusterCharm)
