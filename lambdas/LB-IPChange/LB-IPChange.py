'''
loadbalancers = aws elb describe-load-balancers
for lb in loadbalancers:
    iplist = nslookup lb
    existingiplist = get_iplist_bylb_fromdynamodb
    if len(existingiplist) == 0 or iplist != existingiplist:
        write iplist to cwlog /aws/lambda/ELB-IPChange
        put_metric_data
        send_sns_alert_to_sns_topic(lb dns name A record, existingiplist, iplist)
'''
import sys
sys.path.insert(0, "./lib")

import boto3
import json
import dns.resolver
import os
from datetime import datetime

# Crash the lambda straight away if the environment variables are missing?
DYNTABLE_NAME = os.environ["DYNTABLE_NAME"]
TOPICARN = os.environ["TOPICARN"]
ACCOUNTID = os.environ["ACCOUNTID"]

ACCOUNT_ALIASES = {
    '1232': 'Nonprod-semiauto',
    '1232': 'Nonprod-auto',
    '1232': 'Nonprod-services'
}


def _get_alias_by_accountId(AccountId):
    """
    FIXME Need a better way to provide this information - it's platform-wide, making this a maintenance hassle.
    """
    if AccountId in ACCOUNT_ALIASES:
        return ACCOUNT_ALIASES[AccountId]
    return AccountId


def _get_all_lb():
    client = boto3.client('elb')
    response = client.describe_load_balancers()
    loadbalancers = []
    for lb in response['LoadBalancerDescriptions']:
        loadbalancers.append(lb['DNSName'])
    return loadbalancers


def _dns_lookup(lbdomainname):
    lookup_result_list = []
    myResolver = dns.resolver.Resolver()
    lookupAnswer = myResolver.query(lbdomainname, 'A')
    for answer in lookupAnswer:
        lookup_result_list.append(str(answer))
    print("DNS lookup for {} is {}".format(lbdomainname, lookup_result_list))
    return lookup_result_list


def _get_existingiplist(lbdomainname):
    print("Querying DynamoDB existing IP List for Load Balancer {}".format(lbdomainname))
    dynClient = boto3.client("dynamodb")
    response = dynClient.query(
        TableName=DYNTABLE_NAME,
        Select='SPECIFIC_ATTRIBUTES',
        AttributesToGet=[
            'lbdomainname',
            'iplist'
        ],
        ConsistentRead=True,
        KeyConditions={
            'lbdomainname': {
                'AttributeValueList': [{'S': lbdomainname}],
                'ComparisonOperator': 'EQ'
            }
        }
    )
    print("_get_existingiplist {}".format(response))
    iplist = []
    if response['Count'] > 0:
        iplist = response['Items'][0]['iplist']['S'].split(',')
    return iplist


def _update_iplist(lbdomainname, iplist):
    print("Updating Load Balancer {} with IP List {}".format(lbdomainname, iplist))
    dynClient = boto3.client("dynamodb")
    response = dynClient.update_item(
        ExpressionAttributeNames={
            '#IP': 'iplist',
            '#when': 'updated_at'
        },
        ExpressionAttributeValues={
            ':t': {
                'S': ",".join(iplist),
            },
            ':w': {
                'S': str(datetime.utcnow())
            }
        },
        Key={
            'lbdomainname': {
                'S': lbdomainname,
            }
        },
        ReturnValues='ALL_NEW',
        TableName=DYNTABLE_NAME,
        UpdateExpression='SET #IP = :t, #when = :w'
    )

    print("_update_iplist {}".format(response))
    return response


def _put_metric_data(lbdomainname, iplist):
    cwclient = boto3.client("cloudwatch")
    cwclient.put_metric_data(
        Namespace='AWS/ApplicationELB',
        MetricData=[
            {
                'MetricName': "LoadBalancerIPCount",
                'Dimensions': [
                    {
                        'Name': 'LoadBalancerName',
                        'Value': lbdomainname
                    },
                ],
                'Value': len(iplist),
                'Unit': 'Count'
            },
        ]
    )


def _notify_ops_team(lbdomainname, existingiplist, iplist):
    print("Notifying Ops Team: Change of IPs for Load Balancer {} is detected. Existing IP List: {} . New IP List: {}".format(lbdomainname, existingiplist, iplist))
    client = boto3.client("sns")
    iplist = ",".join(iplist)
    existingiplist = ",".join(existingiplist) if existingiplist else ""
    client.publish(
        TopicArn=TOPICARN,
        Subject='WARNING={}=Loadbalancer=IPChanges'.format(_get_alias_by_accountId(ACCOUNTID)),
        Message='Change of IPs for Load Balancer {} is detected. Existing IP List: {} . New IP List: {}'.format(
            lbdomainname,
            existingiplist,
            iplist
        )
    )


def main():
    loadbalancers = _get_all_lb()
    if len(loadbalancers) > 0:
        for lbdomainname in loadbalancers:
            iplist = _dns_lookup(lbdomainname)
            existingiplist = _get_existingiplist(lbdomainname)
            if set(iplist) != set(existingiplist):
                _update_iplist(lbdomainname, iplist)
                print("IP Changes {} for Loadbalancer {}".format(",".join(iplist), lbdomainname))
                _put_metric_data(lbdomainname, iplist)
                _notify_ops_team(lbdomainname, existingiplist, iplist)


def handler(event, context):
    """
    Lambda handler function.
    FIXME Recommend installing common-pip-log and using that in place of print.
    """
    print('handler event={}'.format(json.dumps(event)))
    return main()


if __name__ == "__main__":
    main()
