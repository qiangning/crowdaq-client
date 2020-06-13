#!/usr/bin/env python3
import json

import click
import logging
from os import path
from mturk_utils import *
import xml.etree.cElementTree as ET
from tqdm import tqdm
from math import ceil
from collections import defaultdict
from datetime import datetime,timedelta


@click.group()
@click.option("--debug", is_flag=True)
@click.option("--production", is_flag=True)
@click.option('--profile', '-p', help="Which AWS profile to use.",
              default="default")
@click.pass_context
def cli(ctx, debug, production, profile):
    if debug:
        logging.basicConfig(level=logging.DEBUG)

    ctx.ensure_object(dict)
    ctx.obj['aws_profile'] = profile


def parse_mturk_params(config_file):
    with open(config_file) as f:
        conf = json.load(f)

    mturk_config = conf['mturk_config']
    meta = conf['meta']

    # Qualification for US
    qualification_requirements = []
    if mturk_config['require_US']:
        qualification_requirements.append(
            {
                'QualificationTypeId': '00000000000000000071',
                'Comparator': 'EqualTo',
                'LocaleValues': [{
                    'Country': 'US'
                }]
            })
    # Qualification for master
    if mturk_config['require_master']:
        prod_masters_qualification = {
            'QualificationTypeId': '2F1QJWKUDD8XADTFD2Q0G6UTO95ALH',
            'Comparator': 'Exists',
        }
        sandbox_masters_qualification = {
            'QualificationTypeId': '2ARFPLSP75KLA8M8DH1HTEQVJT3SY6',
            'Comparator': 'Exists',
        }
        qualification_requirements.append(
            sandbox_masters_qualification
            if mturk_config['sandbox']
            else prod_masters_qualification)

    if mturk_config['other_qualifications']:
        qualification_requirements += mturk_config['other_qualifications']
    print("Qualification requirements:", qualification_requirements)

    return mturk_config, meta, qualification_requirements


def build_external_url_question(
        external_url,
        height=1600,
        ext_question_xmlns="http://mechanicalturk.amazonaws.com/AWSMechanicalTurkDataSchemas/2006-07-14/ExternalQuestion.xsd"
    ):
    EQ_ROOT = ET.Element("ExternalQuestion")
    EQ_ROOT.set("xmlns", ext_question_xmlns)

    external_url = f"{external_url}"
    external_url_node = ET.SubElement(EQ_ROOT, "ExternalURL")
    external_url_node.text = external_url
    frame_height_node = ET.SubElement(EQ_ROOT, "FrameHeight")
    frame_height_node.text = f"{height}" 

    question_xml = f"""<?xml version="1.0" encoding="UTF-8"?>

    {ET.tostring(EQ_ROOT).decode('utf-8')}
    """

    return question_xml


@cli.command('launch-task')
@click.argument('config_file')
@click.option('--url_file', default=None)
@click.option('--url','-u',default=None)
@click.option('--logdir','-l',default=None)
@click.pass_context
def launch_hits(ctx, config_file, url_file, url, logdir):
    click.echo('Launching hits on MTurk\n')
    mturk_config, meta, qualification_requirements \
        = parse_mturk_params(config_file)
    client = getClientFromProfile(
        profile=ctx.obj['aws_profile'],
        sandbox=mturk_config['sandbox'])

    external_hit_urls = []

    if url:
        external_hit_urls = [url]
    elif url_file:
        with open(url_file) as input_fd:
            for line in input_fd:
                line = line.strip()
                if len(line) == 0:
                    continue
                external_hit_urls.append(line)
    else:
        print('Missing url or url files.')
        return

    print("Available balance before launch:",
          client.get_account_balance()['AvailableBalance'])

    expected_cost = mturk_config['reward_per_hit']
    overhead = 1.2
    if mturk_config['require_master']:
        overhead += 0.05
    expected_cost *= overhead*len(external_hit_urls)*mturk_config['num_of_hits']

    print(f"Expected cost: ${expected_cost:.2f}")
    num_of_hits_per_url = 1
    if mturk_config['num_of_hits']:
        num_of_hits_per_url = mturk_config['num_of_hits']

    print(f"You are about to launch {len(external_hit_urls)*num_of_hits_per_url} hit(s)")
    if len(external_hit_urls)>10:
        print(f"Here're the first few:")
    print("\n".join(external_hit_urls[:10]))
    input("Now please go to these links to check if the pages are correct,"
          " and hit [Enter] to continue.")

    all_urls = set()
    if mturk_config['sandbox'] and len(external_hit_urls)>100:
        print("This is launching to the sandbox. Limiting hit to 100.")
        external_hit_urls = external_hit_urls[:100]

    hitgroup_hitids = defaultdict(list)
    for ext_hit_url in tqdm(external_hit_urls):
        eqxml = build_external_url_question(ext_hit_url)
        new_hit = None
        for _ in range(num_of_hits_per_url):
            try:
                new_hit = client.create_hit(
                    Title=meta['title'],
                    Description=meta['description'],
                    Keywords=meta['keywords'],
                    Reward=str(mturk_config['reward_per_hit']),
                    MaxAssignments=1,
                    LifetimeInSeconds=eval(mturk_config['lifetime_min']) * 60,
                    AssignmentDurationInSeconds=eval(
                        mturk_config['session_duration_min']
                    ) * 60,
                    AutoApprovalDelayInSeconds=eval(
                        mturk_config['auto_approval_min']
                    ) * 60,
                    Question=eqxml,
                    QualificationRequirements=qualification_requirements,
                )
                if not new_hit:
                    print('Unexpected failure in hit creation.')
                    print(ext_hit_url)
                    continue
                hitgroup_hitids[new_hit['HIT']['HITGroupId']].append({
                    'hitid':new_hit['HIT']['HITId'],
                    'start-time': str(datetime.now()),
                    'expire-at': str(datetime.now()+timedelta(minutes=eval(mturk_config['lifetime_min'])))
                })
                url_prefix = "workersandbox" if mturk_config['sandbox'] else "worker"
                group_id = new_hit["HIT"]["HITGroupId"]
                url = \
                    f"https://{url_prefix}.mturk.com/mturk/preview?groupId={group_id}"
                all_urls.add(url)
            except:
                print('Unexpected failure in hit creation.')
                print(ext_hit_url)

    print("MTurk job url is:")
    for url in sorted(list(all_urls)):
        print(f"{url}")
    print("Available balance after launch:",
          client.get_account_balance()['AvailableBalance'])
    if logdir:
        print(f'Saving group IDs and hit IDs to {logdir}/...')
        for groupid, hitids in hitgroup_hitids.items():
            log = {'mturk-config':mturk_config, 'meta':meta, 'qualifications':qualification_requirements,
                   'groupId':groupid, 'hitIds':[]}
            try:
                with open(path.join(logdir, groupid + '.json')) as f:
                    oldlog = json.load(f)
                    assert log['mturk-config']==oldlog['mturk-config']
                    assert log['meta']==oldlog['meta']
                    assert log['qualifications']==oldlog['qualifications']
                    assert log['groupId']==oldlog['groupId']
                    log['hitIds']+=oldlog['hitIds']
            except: pass
            log['hitIds']+=hitids

            with open(path.join(logdir, groupid+'.json'), 'w') as f:
                json.dump(log,f,indent=2,sort_keys=True)


@cli.command()
@click.argument('groupid')
@click.option('--sandbox/--real', '-s/-r', default=True)
@click.option('--qualid', '-q', default='')
@click.option('--logdir', '-l', default=None)
@click.option('--clean', '-c', is_flag=True)
@click.pass_context
def expire_hit_group(ctx, groupid, sandbox, qualid, logdir, clean):
    click.echo(f'Expiring hit group {groupid} on MTurk')
    wanted_hit_ids = []
    use_log = not clean and logdir and path.exists(path.join(logdir,groupid+'.json'))
    if use_log:
        with open(path.join(logdir,groupid+'.json')) as f:
            log = json.load(f)
            client = getClientFromProfile(ctx.obj['aws_profile'], sandbox=log['mturk-config']['sandbox'])
            wanted_hit_ids = [x['hitid'] for x in log['hitIds'] if datetime.fromisoformat(x['expire-at'])>datetime.now()]
    else:
        client = getClientFromProfile(ctx.obj['aws_profile'], sandbox=sandbox)
        wanted_hit_ids, _ = list_hits_with_groupid(client, groupid, qual_id=qualid)

    hits_stopped = set()
    for hit_id in wanted_hit_ids:
        try:
            client.update_expiration_for_hit(HITId=hit_id, ExpireAt=0)
            hit = client.get_hit(HITId=hit_id)
            new_expiry_date = hit['HIT']['Expiration']
            print(f"{hit_id} will now expire at {new_expiry_date}")
            hits_stopped.add(hit_id)
        except: pass

    if use_log:
        for hit in log['hitIds']:
            if hit['hitid'] in hits_stopped:
                hit['expire-at'] = str(datetime.now())
        with open(path.join(logdir,groupid+'.json'), 'w') as f:
            json.dump(log,f,indent=2,sort_keys=True)


@cli.command('assign-qual')
@click.argument('qualid')
@click.argument('report')
@click.argument('passing_grade',type=float)
@click.option('--sandbox/--real', '-s/-r', default=True)
@click.option('--dryrun', '-d', is_flag=True)
@click.option('--verbose', '-v', is_flag=True)
@click.pass_context
def give_qualifications_from_exam(ctx, qualid, report, passing_grade, sandbox, dryrun, verbose):
    click.echo(f'Assigning qualification {qualid} to workers with grade higher or equal to {passing_grade} in report {report}\n')

    with open(report) as f:
        report = json.load(f)
    if passing_grade>1:
        print('Passing grade should be in [0,1]')
        return

    workerIds = [r['worker_id'] for r in report['grades'] if r['grade']>=passing_grade]
    grades = [ceil(r['grade']*100) for r in report['grades'] if r['grade'] >= passing_grade]

    client = getClientFromProfile(ctx.obj['aws_profile'], sandbox=sandbox)
    grant_qualification_to_workers(client, qualid, workerIds, grades, dryrun=dryrun, verbose=verbose)
    return get_workerids_with_qualification_type(client,qualid)



if __name__ == '__main__':
    cli()
