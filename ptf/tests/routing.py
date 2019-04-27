# Copyright 2019-present Open Networking Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# ------------------------------------------------------------------------------
# IPV6 ROUTING TESTS
#
# To run all tests:
#     make routing
# ------------------------------------------------------------------------------

from ptf.testutils import group

from lib.base_test import *


@group("routing")
class IPv6RoutingTest(P4RuntimeTest):
    """Tests basic IPv6 routing"""

    def runTest(self):
        for pkt_type in ["tcpv6", "udpv6", "icmpv6"]:
            print_inline("%s ... " % pkt_type)
            pkt = getattr(testutils, "simple_%s_packet" % pkt_type)()
            self.testPacket(pkt)

    @autocleanup
    def testPacket(self, pkt):
        next_hop_mac = SWITCH2_MAC

        # Add table entry which handles packet with destination mac equals to router mac (my station mac)
        # Consider pkt's mac dst addr as my station address
        # ---- START SOLUTION ----
        self.insert(self.helper.build_table_entry(
            table_name="FabricIngress.l2_my_station",
            match_fields={
                # Exact match.
                "hdr.ethernet.dst_addr": pkt[Ether].dst
            },
            action_name="NoAction"
        ))
        # ---- END SOLUTION ----

        # Insert ECMP group with only one member (next_hop_mac)
        # ---- START SOLUTION ----
        self.insert(self.helper.build_act_prof_group(
            act_prof_name="FabricIngress.ecmp_selector",
            group_id=1,
            actions=[
                # List of tuples (action name, action param dict)
                ("FabricIngress.set_l2_next_hop", {"dmac": next_hop_mac}),
            ]
        ))
        # ---- END SOLUTION ----

        # Map pkt's IPv6 dst addr to group
        # ---- START SOLUTION ----
        self.insert(self.helper.build_table_entry(
            table_name="FabricIngress.l3_table",
            match_fields={
                # LPM match (value, prefix)
                "hdr.ipv6.dst_addr": (pkt[IPv6].dst, 128)
            },
            group_id=1
        ))
        # ---- END SOLUTION ----

        # Map next_hop_mac to output port
        # ---- START SOLUTION ----
        self.insert(self.helper.build_table_entry(
            table_name="FabricIngress.l2_exact_table",
            match_fields={
                # Ternary match.
                "hdr.ethernet.dst_addr": next_hop_mac
            },
            action_name="FabricIngress.set_output_port",
            action_params={
                "port_num": self.port2
            }
        ))
        # ---- END SOLUTION ----

        # Expected pkt should have routed MAC addresses and decremented TTL
        exp_pkt = pkt.copy()
        pkt_route(exp_pkt, next_hop_mac)
        pkt_decrement_ttl(exp_pkt)

        testutils.send_packet(self, self.port1, str(pkt))
        testutils.verify_packet(self, exp_pkt, self.port2)


@group("routing")
class NdpReplyGenTest(P4RuntimeTest):
    """Tests automatic generation of NDP Neighbor Advertisement for IPV6 address
    associated to the switch interface."""

    @autocleanup
    def runTest(self):
        switch_ip = SWITCH1_IPV6
        switch_mac = SWITCH1_MAC

        # Insert entry to transform NDP NA packets for the given target address
        # (match), to NDP NA packes with the give target MAC address (action)
        self.insert(self.helper.build_table_entry(
            table_name="FabricIngress.ndp_reply",
            match_fields={
                # Exact match.
                "hdr.ndp.target_addr": switch_ip
            },
            action_name="FabricIngress.ndp_advertisement",
            action_params={
                "router_mac": switch_mac
            }
        ))

        # NDP Neighbor Solicitation packet
        pkt = genNdpNsPkt(target_ip=switch_ip)

        # NDP Neighbor Advertisement packet
        exp_pkt = genNdpNaPkt(target_ip=switch_ip,
                              target_mac=switch_mac,
                              src_mac=switch_mac,
                              src_ip=switch_ip,
                              dst_ip=pkt[IPv6].src)

        # Send NDP NS, expect NDP NA from the same port.
        testutils.send_packet(self, self.port1, str(pkt))
        testutils.verify_packet(self, exp_pkt, self.port1)
