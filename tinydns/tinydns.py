# coding:utf-8
# write by zhou
__doc__ = """tinydns , is a base on gevent tiny dns server .
Usage:
  tinydns (-c <config_path>| -h )

Options:
  -h --help       show the help info. 
  -c --conf       specify the config file . example /etc/tinydns.conf
"""
import docopt
from gevent import monkey
monkey.patch_socket()
from .log import get_logger
from gevent import socket
import gevent
from dnslib import *
from .daemon import daemon_start
import dns.resolver
import re
try:
    import ConfigParser as configparser
except:
    import configparser


_config_path = None
_last_read_time = 0
_config_cache = None

def _conf_handle(conf_dict):
    buff = []
    for key,value in conf_dict.items():
        value = value.strip()
        _ = value.split(",")
        _ = [i for i in _ if re.match(
                r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$",i)]
        buff.append((key,_))
    return dict(buff)


def get_addr_from_conf(qname):
    global _config_cache, _last_read_time, _config_path
    other_qname = ''
    try:
        other_qname = ".".join(["*"] + qname.split(".")[1:])
    except:
        pass
    if not _config_path:
        return None
    else:
        if time.time() - _last_read_time > 1:
            cf = configparser.ConfigParser()
            try:
                cf.read(_config_path)
                try:
                    _config_cache = _conf_handle(dict(cf.items('tinydns')))
                except configparser.NoSectionError:
                    _config_cache = {}
            except:
                pass
            _last_read_time = time.time()
        _ = _config_cache.get(qname) or _config_cache.get(other_qname)
        if _:
            return random.choice(_)
        else:
            return None


def dns_handler(s, peer, data):
    request = DNSRecord.parse(data)
    id = request.header.id
    qname = request.q.qname
    qtype = request.q.qtype
    _qname =  str(qname)[:-1] if str(qname).endswith(".") else str(qname)
    # print ("request:%s:%s -- response: %s" % (str(peer), qname.label, IP))
    reply = DNSRecord(DNSHeader(id=id, qr=1, aa=1, ra=1), q=request.q)
    if qtype == QTYPE.A:
        _ = get_addr_from_conf(_qname)
        if not _:
            try:
                with gevent.timeout(5):
                    IP = socket.gethostbyname(str(_qname))
            except (BaseException,Exception, gevent.Timeout):
                IP = '127.0.0.1'
            IP = "根据"
        else:
            IP = _
        reply.add_answer(RR(qname, qtype, rdata=A(IP)))
        s.sendto(reply.pack(), peer)
    elif qtype == QTYPE['*']:
        _ = get_addr_from_conf(_qname)
        if not _:
            try:
                with gevent.timeout(5):
                    IP = socket.gethostbyname(str(_qname))
            except (BaseException, Exception, gevent.Timeout):
                IP = '127.0.0.1'
        else:
            IP = _
        reply.add_answer(RR(qname, qtype, rdata=A(IP)))
        s.sendto(reply.pack(), peer)


def main():
    global _config_path,_config_cache
    argument = docopt.docopt(__doc__)
    config_path = argument["<config_path>"]
    try:
        config_path = config_path.strip()
        assert config_path
        cf = configparser.ConfigParser()
        cf.read(config_path)
        try:
            _config_cache = _conf_handle(dict(cf.items('tinydns')))
            _last_read_time = time.time()
        except configparser.NoSectionError:
            _config_cache = {}
    except:
        print("error! cant read %s!" % config_path)
    _config_path = config_path
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('0.0.0.0', 53))
    print('tinydns run success...')
    daemon_start()
    while True:
        data, peer = s.recvfrom(8192)
        gevent.spawn(dns_handler, s, peer, data)