# -*- coding: utf-8 -*-
"""

@author: Lukas Sandström
"""

import logging
from typing import NoReturn, List

from memoized_property import memoized_property

from .gen import ZVA_gen
from .scpi.class_property import SCPIProperty
from . import znb
from . import network as net


def connect_ethernet(ip_address: str) -> "ZVA":
    """
    Helper to connect to a ZVA VNA via Ethernet / TCPIP / VISA.
    Creates an ZVA instance and calls init() on it before returning.

    :param ip_address: The ip address in string format
    :return: An initialized ZVA instance.
    :rtype: RSSscpi.zva.ZVA
    """
    return net.connect_ethernet(ZVA, ip_address)


class ZVAZeroconf(znb.ZNBZeroconf):
    pass


class ZCListener(net.ZeroconfListener):
    info_class = ZVAZeroconf
    service_name = "_vxi-11._tcp.local."

    def filter_zc_info(self, zc_info):
        return "ZVA" in zc_info.name


def find_zva(max_time=2, max_devices=None):
    """
    Use zeroconf to scan the local network for ZVA VNAs

    :param float max_time: The maximum time we will wait, in seconds
    :param int max_devices: Stop the search after this many devices have been found
    :return: A list of ZVAZeroconf objects describing the found devices.
    :rtype: list[ZVAZeroconf]
    """

    return net.zeroconf_scan(ZCListener(), max_time, max_devices)


class ZVA(znb.ZNB):
    _scpi = ZVA_gen()

    @property
    def scpi(self) -> ZVA_gen:
        return self._scpi

    def __init__(self, visa_res):
        super().__init__(visa_res=visa_res)
        self.logger = logging.getLogger(__name__)
        self.visa_logger = self.logger.getChild("VISA")

    @memoized_property
    def filesystem(self):
        """
        A Filsystem instance which enables filesystem operations on the instrument.

        :rtype: RSSscpi.zva.Filesystem
        """
        return Filesystem(self)

    def _set_codec(self):
        # There is no functionality for this on the ZVA
        assert not hasattr(self.SYSTem.COMMunicate, "CODec")

    def get_channel(self, n: int) -> "Channel":
        return Channel(n, self)

    def get_diagram(self, n):
        """
        Returns a :class:`RSSscpi.zva.Diagram` instance, linked to the instrument.

        :param int n: The diagram id, Wnd
        :rtype: RSSscpi.zva.Diagram
        """
        return Diagram(n, self)


class Channel(znb.Channel):
    """
    This class maps to the concept of a channel on the ZVA.
    """

    @property
    def instrument(self) -> ZVA:
        assert isinstance(self._instr, ZVA)
        return self._instr

    @property
    def CALC(self) -> ZVA_gen.CALCulate:
        return self.instrument.CALCulate[self.n]

    @property
    def CONFch(self) -> ZVA_gen.CONFigure.CHANnel:
        return self.instrument.CONFigure.CHANnel[self.n]

    @property
    def SENSe(self) -> ZVA_gen.SENSe:
        return self.instrument.SENSe[self.n]

    @property
    def SOURce(self) -> ZVA_gen.SOURce:
        return self.instrument.SOURce[self.n]

    @property
    def TRIGger(self) -> ZVA_gen.TRIGger:
        return self.instrument.TRIGger[self.n]

    @property
    def sweep(self) -> "Sweep":
        return Sweep(self)

    def get_trace(self, name: str) -> "Trace":
        return Trace(name=name, channel=self)

    def get_vna_port(self, port_no: int):
        return ChannelVNAPort(self, port_no)

    def create_trace(self, name: str, parameter: str, diagram=None) -> "Trace":
        return super(Channel, self).create_trace(name, parameter, diagram)

    def query_trace_list(self) -> List["Trace"]:
        raise NotImplementedError("This method is not available for the ZVA.")


class Diagram(znb.Diagram):
    @property
    def LAYout(self) -> NoReturn:
        raise AttributeError("DISPlay:LAYout is not avalable on ZVA")

    @property
    def WINDow(self) -> ZVA_gen.DISPlay.WINDow:
        return super().WINDow


class Filesystem(ZVA_gen.MMEMory, znb.Filesystem):
    pass


class Limit(ZVA_gen.CALCulate.LIMit, znb.Limit):
    pass


class Marker(ZVA_gen.CALCulate.MARKer, znb.Marker):
    pass


class ChannelVNAPort(znb.ChannelVNAPort):
    @property
    def SOURcePOWer(self) -> ZVA_gen.SOURce.POWer:
        return super().SOURcePOWer

    @property
    def src_attenuator(self):
        """
        Sets/queries the source attenuator value. If the attenuator setting is in auto mode,
        the current value of the attenuator will be returned.

        SOURce:POWer:ATTenuation / SOURce:POWer:ATTenuation:AUTO:VALue?
        """
        return int(self.SOURcePOWer.ATTenuation.AUTO.VALue.q())

    @src_attenuator.setter
    def src_attenuator(self, att):
        # TODO: check that the att parameter is within the range of the instrument
        self.SOURcePOWer.ATTenuation.w(int(att))

    src_attenuator_mode = SCPIProperty(ZVA_gen.SOURce.POWer.ATTenuation.MODE, str, parent_prop=SOURcePOWer)
    """AUTO | MANual | LNOise"""


class Sweep(znb.Sweep):
    def __init__(self, channel):
        super(Sweep, self).__init__(channel=channel)
        self.segments = SweepSegments(self)

    @property
    def INITiate(self) -> ZVA_gen.INITiate:
        return super().INITiate

    @property
    def SWEep(self) -> ZVA_gen.SENSe.SWEep:
        return super().SWEep

    @property
    def dwell_on_each_partial_measurement(self):
        """
        The ZVA does not support setting dwell time on only the first partial measurement.
        """
        return True

    def get_segment(self, n):
        # type: (int) -> SweepSegment
        return SweepSegment(n, self.channel)


class SweepSegment(ZVA_gen.SENSe.SEGMent, znb.SweepSegment):

    @property
    def analog_sweep_is_enabled(self):
        """The ZVA does not support ANALog sweeps"""
        return False


class SweepSegments(znb.SweepSegments):
    def insert_segment(self, start_freq, stop_freq, points, ifbw, power, time="AUTO", lo_sideband="AUTO",
                       if_selectivity="NORMal", analog_sweep=False, position=1):
        """
        :param float start_freq: Segment start frequency in Hz
        :param float stop_freq: Segment stop frequency in Hz
        :param int points: Number of sweep points in the segment
        :param float ifbw: IF bandwidth
        :param float power: Segment source power in dBm
        :param float time: Segment sweep time or segment dwell time in seconds
        :param str lo_sideband: "POSitive" | "NEGative" | "AUTO" (default)
        :param str if_selectivity: "NORMal" (default) | "MEDium" | "HIGH"
        :param bool analog_sweep: For code compatibility with ZNB. Must be set to False.
        :param int position: The position in the segment list which the created segment will be inserted at. Default is 1 (top).
        :return: The newly created segment
        :rtype: SweepSegment
        """
        if analog_sweep:
            raise ValueError("The ZVA does not support analog sweeps.")
        self._SEG[position].INSert.w(start_freq, stop_freq, points, power, time, "0", ifbw, lo_sideband, if_selectivity)
        return self.get_segment(position)


class Trace(znb.Trace):
    def get_marker(self, n):
        return Marker(n, self)

    def copy(self, new_name: str, diagram=None) -> "Trace":
        return super(Trace, self).copy(new_name, diagram)

    def copy_assign_math(self, new_name: str, equation: str, diagram=None) -> "Trace":
        return super(Trace, self).copy_assign_math(new_name, equation, diagram)

    def query_diagram(self) -> NoReturn:
        raise NotImplementedError("The ZVA does not support CONF:TRAC:WIND?")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print([str(x) for x in find_zva(max_devices=10, max_time=1)])
