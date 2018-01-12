
# Copyright IBM Corp, All Rights Reserved.
#
# SPDX-License-Identifier: Apache-2.0
#
import logging
import os
import sys
import uuid

from flask import jsonify, Blueprint, render_template
from flask import request as r
import json

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from common import log_handler, LOG_LEVEL, \
    make_ok_resp, make_fail_resp, \
    CODE_CREATED, \
    request_debug

from modules import host_handler
from modules.models import Cluster as ClusterModel
from modules.models import Host as HostModel
from agent import detect_daemon_type

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)
logger.addHandler(log_handler)


bp_host_api = Blueprint('bp_host_api', __name__,
                        url_prefix='/{}'.format("api"))


@bp_host_api.route('/hosts', methods=['GET'])
def hosts_list():
    logger.info("/hosts_list method=" + r.method)
    request_debug(r, logger)
    col_filter = dict((key, r.args.get(key)) for key in r.args)
    items = list(host_handler.list(filter_data=col_filter))

    return make_ok_resp(data=items)


@bp_host_api.route('/host/<host_id>', methods=['GET'])
def host_query(host_id):
    request_debug(r, logger)
    result = host_handler.get_by_id(host_id)
    logger.debug(result)
    if result:
        return make_ok_resp(data=result)
    else:
        error_msg = "host not found with id=" + host_id
        logger.warning(error_msg)
        return make_fail_resp(error=error_msg, data=r.form)


@bp_host_api.route('/host', methods=['POST'])
def host_create():
    request_debug(r, logger)
    name, worker_api, capacity, log_type, log_server, log_level, host_type = \
        r.form['name'], r.form['worker_api'], r.form['capacity'], \
        r.form['log_type'], r.form['log_server'], r.form['log_level'], \
        r.form['host_type'] if 'host_type' in r.form else None

    if "autofill" in r.form and r.form["autofill"] == "on":
        autofill = "true"
    else:
        autofill = "false"

    if "schedulable" in r.form and r.form["schedulable"] == "on":
        schedulable = "true"
    else:
        schedulable = "false"

    if host_type == "vsphere":
        vcaddress = r.form['vc_address']
        if vcaddress.find(":") == -1:
            address = vcaddress
            port = "443"
        else:
            address = vcaddress.split(':')[0]
            port = vcaddress.split(':')[1]
        logger.debug("address={}, port={}".format(address, port))

        vmname = "cello-vsphere-" + str(uuid.uuid1())
        vsphere_param = {
            'vc': {
                'address': address,
                'port': port,
                'username': r.form['vc_user'],
                'password': r.form['vc_password'],
                'network': r.form['vc_network'],
                'vc_datastore': r.form['datastore'],
                'vc_datacenter': r.form['datacenter'],
                'vc_cluster': r.form['cluster'],
                'template': r.form['vm_template']},
            'vm': {
                'vmname': vmname,
                'ip': r.form['vm_ip'],
                'gateway': r.form['vm_gateway'],
                'netmask': r.form['vm_netmask'],
                'dns': r.form['vm_dns'],
                'vcpus': int(r.form['vm_cpus']),
                'memory': int(r.form['vm_memory'])}}

        logger.debug("name={}, capacity={},"
                     "fillup={}, schedulable={}, log={}/{}, vsphere_param={}".
                     format(name, capacity, autofill, schedulable,
                            log_type, log_server, vsphere_param))

        vsphere_must_have_params = {
            'Name': name,
            'Capacity': capacity,
            'LoggingType': log_type,
            'VCAddress': address,
            'VCUser': r.form['vc_user'],
            'VCPassword': r.form['vc_password'],
            'VCNetwork': r.form['vc_network'],
            'Datastore': r.form['datastore'],
            'Datacenter': r.form['datacenter'],
            'Cluster': r.form['cluster'],
            'VMIp': r.form['vm_ip'],
            'VMGateway': r.form['vm_gateway'],
            'VMNetmask': r.form['vm_netmask']}
        for key in vsphere_must_have_params:
            if vsphere_must_have_params[key] == '':
                error_msg = "host POST without {} data".format(key)
                logger.warning(error_msg)
                return make_fail_resp(error=error_msg, data=r.form)
        result = host_handler.create(name=name, worker_api=worker_api,
                                     capacity=int(capacity),
                                     autofill=autofill,
                                     schedulable=schedulable,
                                     log_level=log_level,
                                     log_type=log_type,
                                     log_server=log_server,
                                     host_type=host_type,
                                     params=vsphere_param)
    else:
        logger.debug("name={}, worker_api={}, capacity={}"
                     "fillup={}, schedulable={}, log={}/{}".
                     format(name, worker_api, capacity, autofill, schedulable,
                            log_type, log_server))
        if not name or not worker_api or not capacity or not log_type:
            error_msg = "host POST without enough data"
            logger.warning(error_msg)
            return make_fail_resp(error=error_msg, data=r.form)
        else:
            host_type = host_type if host_type \
                else detect_daemon_type(worker_api)
            result = host_handler.create(name=name, worker_api=worker_api,
                                         capacity=int(capacity),
                                         autofill=autofill,
                                         schedulable=schedulable,
                                         log_level=log_level,
                                         log_type=log_type,
                                         log_server=log_server,
                                         host_type=host_type)
    logger.debug("result.msg={}".format(result.get('msg')))
    if (host_type == "vsphere") and ('msg' in result):
        vsphere_errmsg = result.get('msg')
        error_msg = "Failed to create vsphere host {}".format(vsphere_errmsg)
        logger.warning(error_msg)
        return make_fail_resp(error=error_msg)
    elif result:
        logger.debug("host creation successfully")
        return make_ok_resp(code=CODE_CREATED)
    else:
        error_msg = "Failed to create host {}".format(r.form["name"])
        logger.warning(error_msg)
        return make_fail_resp(error=error_msg)


@bp_host_api.route('/host', methods=['PUT'])
def host_update():
    request_debug(r, logger)
    if "id" not in r.form:
        error_msg = "host PUT without enough data"
        logger.warning(error_msg)
        return make_fail_resp(error=error_msg,
                              data=r.form)
    else:
        id, d = r.form["id"], {}
        for k in r.form:
            if k != "id":
                d[k] = r.form.get(k)
        result = host_handler.update(id, d)
        if result:
            logger.debug("host PUT successfully")
            return make_ok_resp()
        else:
            error_msg = "Failed to update host {}".format(result.get("name"))
            logger.warning(error_msg)
            return make_fail_resp(error=error_msg)


@bp_host_api.route('/host', methods=['PUT', 'DELETE'])
def host_delete():
    request_debug(r, logger)
    request_data = r.get_json(force=True, silent=True)
    if "id" in r.form:
        host_id = r.form["id"]
    elif "id" in request_data:
        host_id = request_data.get("id")
    else:
        error_msg = "host delete without enough data"
        logger.warning(error_msg)
        return make_fail_resp(error=error_msg, data=r.form)

    logger.debug("host delete with id={0}".format(host_id))
    if host_handler.delete(id=host_id):
        return make_ok_resp()
    else:
        error_msg = "Failed to delete host {}".format(host_id)
        logger.warning(error_msg)
        return make_fail_resp(error=error_msg)


@bp_host_api.route('/host_op', methods=['POST'])
def host_actions():
    logger.info("/host_op, method=" + r.method)
    request_debug(r, logger)

    host_id, action = r.form['id'], r.form['action']
    if not host_id or not action:
        error_msg = "host POST without enough data"
        logger.warning(error_msg)
        return make_fail_resp(error=error_msg,
                              data=r.form)
    else:
        if action == "fillup":
            if host_handler.fillup(host_id):
                logger.debug("fillup successfully")
                return make_ok_resp()
            else:
                error_msg = "Failed to fillup the host."
                logger.warning(error_msg)
                return make_fail_resp(error=error_msg, data=r.form)
        elif action == "clean":
            if host_handler.clean(host_id):
                logger.debug("clean successfully")
                return make_ok_resp()
            else:
                error_msg = "Failed to clean the host."
                logger.warning(error_msg)
                return make_fail_resp(error=error_msg, data=r.form)
        elif action == "reset":
            if host_handler.reset(host_id):
                logger.debug("reset successfully")
                try:
                    host_model = HostModel.objects.get(id=host_id)
                    clusters = ClusterModel.objects(host=host_model)
                    for cluster_item in clusters:
                        cluster_item.delete()
                except Exception:
                    pass
                return make_ok_resp()
            else:
                error_msg = "Failed to reset the host."
                logger.warning(error_msg)
                return make_fail_resp(error=error_msg, data=r.form)

    error_msg = "unknown host action={}".format(action)
    logger.warning(error_msg)
    return make_fail_resp(error=error_msg, data=r.form)
