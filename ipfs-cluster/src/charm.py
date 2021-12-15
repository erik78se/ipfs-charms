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
from ops.model import ActiveStatus, BlockedStatus, WaitingStatus, MaintenanceStatus
import subprocess
import sys
import jinja2
import json
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
        self.framework.observe(self.on.stop, self._on_stop)
        self.framework.observe(self.on.update_status, self._on_update_status)


        # Peer relation
        self.framework.observe(self.on.replicas_relation_joined, self._on_replicas_relation_joined)
        self.framework.observe(self.on.replicas_relation_departed, self._on_replicas_relation_departed)
        self.framework.observe(self.on.replicas_relation_changed, self._on_replicas_relation_changed)


        self._stored.set_default(service_sources_uri=self.config["service-sources-uri"],
                                 ctl_sources_uri=self.config["ctl-sources-uri"],
                                 restart_on_reconfig=self.config["restart-on-reconfig"],
                                 leader_ip=None,
                                 cluster_secret=None,
                                 identity_id=None,
                                 has_peers=False)


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

        # Do the init - produces the service.json and other configs
        # ./ipfs-cluster-service init
        # configuration written to /home/ubuntu/.ipfs-cluster/service.json
        # new identity written to /home/ubuntu/.ipfs-cluster/identity.json
        # new empty peerstore written to /home/ubuntu/.ipfs-cluster/peerstore
        os.system('sudo -u ubuntu /opt/ipfs/ipfs-cluster-service/ipfs-cluster-service init --force')


    def _on_config_changed(self, event):
        """
        Update configs.
        """
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)
        if not self._stored.cluster_secret:
            self.unit.status = BlockedStatus("Missing secret for config.")
            logger.error("Hold up start, missing cluster secret.")
        else:
            utils.write_service_json({'cluster_secret': self._stored.cluster_secret})
        
        self._on_update_status(event)

    def _on_start(self, event):
        """
            Start your service here, possibly defer (wait) until conditions are OK.
        """
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)
        logger.info(f"{EMOJI_GREEN_DOT} Starting ipfs-cluster.service")

        # If no peers, just start as we are.
        if self.model.unit.is_leader():
            os.system('systemctl start ipfs-cluster.service')
        else:
            # Wait until there is a peerstore file
            if not self._stored.has_peers:
                self.unit.status = BlockedStatus("Has no peers.")
                logger.info("Hold up start, waiting for peerstore file.")
                event.defer()
                return
            elif not self._stored.cluster_secret:
                self.unit.status = BlockedStatus("Missing secret for config.")
                logger.info("Hold up start, missing cluster secret.")
                event.defer()
                return
            else:
                utils.write_service_json({'cluster_secret': self._stored.cluster_secret})
                os.system('systemctl start ipfs-cluster.service')
            
        # Calling update_status gives quick feedback when deploying starts up.
        self._on_update_status(event)
        self.unit.set_workload_version(utils.getIpfsClusterVersion())


    def _on_leader_elected(self, event):
        """
            This is only run on the unit which is selected by juju as leader.
        """
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)
        peer_relation = self.model.get_relation("replicas")
        ip = str(self.model.get_binding(peer_relation).network.bind_address)

        # Pick up values from generated files if we don't have it stored.
        if not self._stored.cluster_secret:
            self._stored.cluster_secret = utils.get_cluster_secret()
        if not self._stored.identity_id:
            self._stored.identity_id = utils.get_identity_id()
            
        peer_relation.data[self.app].update({"leader-ip": ip})
        peer_relation.data[self.app].update({"secret": self._stored.cluster_secret})
        peer_relation.data[self.app].update({"id": self._stored.identity_id})

    def _on_update_status(self, event):
        """
        Tell the world.
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
        
    def _on_stop(self, event):
        """
        Bring down your service, possibly defer until all systems are good to go similar to start hook.
        """
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)

        logger.info(f"{EMOJI_RED_DOT} Stopping the ipfs-cluster service...")
        os.system('systemctl stop ipfs-cluster.service')


    def _on_replicas_relation_joined(self, event):
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)

        """Handle relation-joined event for the replicas relation"""
        logger.debug("Hello from %s to %s", self.unit.name, event.unit.name)

        # Check if we're the leader, meaning we are responsible
        # for sending config. No peerstore expected to exists for
        # leader, so only set local store values.
        if self.unit.is_leader():
            ip = str(self.model.get_binding(event.relation).network.bind_address)
            logging.debug("Leader %s setting some data!", self.unit.name)
            event.relation.data[self.app].update({"leader-ip": ip})
            event.relation.data[self.app].update({"secret": self._stored.cluster_secret})
            event.relation.data[self.app].update({"id": str(self._stored.identity_id)})
        else:
                self.writePeerStore()
                self._stored.has_peers = True

    def _on_replicas_relation_departed(self, event):
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)
        logger.debug("Goodbye from %s to %s", self.unit.name, event.unit.name)

    def _on_replicas_relation_changed(self, event):
        logger.debug(EMOJI_CORE_HOOK_EVENT + sys._getframe().f_code.co_name)

        logging.debug("Unit %s can see the following data: %s", self.unit.name, event.relation.data.keys())
        # {'egress-subnets': '10.166.0.21/32',
        #  'ingress-address': '10.166.0.21',
        #  'private-address': '10.166.0.21',
        #  'unit-data': 'ipfs-cluster/0'},
        #  <ops.model.Application ipfs-cluster>:
        #    {'id': 'someid',
        #     'leader-ip': '10.166.0.21',
        #     'secret': 'somesecret'},
        #  <ops.model.Unit ipfs-cluster/1>:
        #    {'egress-subnets': '10.166.0.20/32',
        #     'ingress-address': '10.166.0.20',
        #     'private-address': '10.166.0.20',
        #     'unit-data': 'ipfs-cluster/1'}}

        # Fetch an item from the application data bucket
        leader_ip_value = event.relation.data[self.app].get("leader-ip")
        cluster_secret = event.relation.data[self.app]['secret']
        identity_id = event.relation.data[self.app]['id']

        valid_relation = True
        
        # Store the latest copy of data locally in our state store
        if leader_ip_value and leader_ip_value != self._stored.leader_ip:
            self._stored.leader_ip = leader_ip_value
        else:
            valid_relation = False
        
        if cluster_secret and cluster_secret != self._stored.cluster_secret:
            self._stored.cluster_secret = cluster_secret
        else:
            valid_relation = False
            
        if identity_id and identity_id != self._stored.identity_id:
            self._stored.identity_id = identity_id
        else:
            valid_relation = False

        # In case we dont have all data needed to write config
        # and start with that, lets defer() and wait.
        if not valid_relation:
            event.defer()
            return

    def writePeerStore(self):
        """
        Write peerstore to file
        """
        peer_relation = self.model.get_relation("replicas")
        identity_id = self._stored.identity_id
            
        with open("/home/ubuntu/.ipfs-cluster/peerstore", "w+") as peerstoreFile:
            for peer in peer_relation.units:
                peer_ip = peer_relation.data[peer].get("ingress-address")
                peerstoreFile.write(f"/ip4/{peer_ip}/tcp/9096/p2p/{identity_id}\n")
        

            
if __name__ == "__main__":
    main(IPFSClusterCharm)
