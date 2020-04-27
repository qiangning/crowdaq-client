#!/usr/bin/env python3
import json

import click
import logging

from mturk_utils import getClientFromProfile, list_hits_with_groupid


@click.group()
@click.option("--debug", is_flag=True, default=False)
@click.option("--production", is_flag=True, default=False)
@click.option('--profile', '-p', help="Which AWS profile to use.", default="default")
@click.pass_context
def cli(ctx, debug, production, profile):
    if debug:
        logging.basicConfig(level=logging.DEBUG)

    ctx.ensure_object(dict)
    ctx.obj['aws_profile'] = profile



@cli.command()
@click.argument('config_file')
@click.argument('exam_page_url')
@click.pass_context
def launch_exam(ctx, config_file, exam_page_url):
    click.echo('Launching Exam on MTurk')

    with open(config_file) as f:
        conf = json.load(f)

    mturk_config = conf['mturk_config']
    client = getClientFromProfile(profile=ctx.obj['aws_profile'], sandbox=mturk_config['sandbox'])

    print("Available balance before launch:", client.get_account_balance()['AvailableBalance'])
    print(f"External url is: {exam_page_url}")
    input("Please check if the page is correct, and hit [Enter] to continue.")

    question_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
                        <ExternalQuestion xmlns="http://mechanicalturk.amazonaws.com/AWSMechanicalTurkDataSchemas/2006-07-14/ExternalQuestion.xsd">
                          <ExternalURL>{exam_page_url}</ExternalURL>
                          <FrameHeight>1600</FrameHeight>
                        </ExternalQuestion>
    '''
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
        qualification_requirements.append(sandbox_masters_qualification if mturk_config['sandbox'] else
                                          prod_masters_qualification)

    if mturk_config['include_qualifications']:
        for qualification_string in mturk_config['include_qualifications']:
            qualification = {
                'QualificationTypeId': qualification_string,
                'Comparator': 'Exists',
                'ActionsGuarded': 'Accept'
            }
            qualification_requirements.append(qualification)

    if mturk_config['exclude_qualifications']:
        for qualification_string in mturk_config['exclude_qualifications']:
            qualification = {
                'QualificationTypeId': qualification_string,
                'Comparator': 'DoesNotExist',
                'ActionsGuarded': 'DiscoverPreviewAndAccept'
            }
            qualification_requirements.append(qualification)
    print("Qualification requirements:", qualification_requirements)
    all_urls = set()
    for qid in range(mturk_config['num_of_hits']):
        new_hit = client.create_hit(
            Title=mturk_config['title'],
            Description=mturk_config['description'],
            Keywords=mturk_config['keywords'],
            Reward=str(mturk_config['reward_per_hit']),
            MaxAssignments=1,
            LifetimeInSeconds=eval(mturk_config['lifetime_min']) * 60,
            AssignmentDurationInSeconds=eval(mturk_config['session_duration_min']) * 60,
            AutoApprovalDelayInSeconds=eval(mturk_config['auto_approval_min']) * 60,
            Question=question_xml,
            QualificationRequirements=qualification_requirements,
        )
        url_prefix = "workersandbox" if mturk_config['sandbox'] else "worker"
        group_id = new_hit["HIT"]["HITGroupId"]
        url = f"https://{url_prefix}.mturk.com/mturk/preview?groupId={group_id}"
        all_urls.add(url)
    print("MTurk job url is:")
    for url in sorted(list(all_urls)):
        print(f"{url}")
    print("Available balance after launch:", client.get_account_balance()['AvailableBalance'])


@cli.command()
@click.argument('groupid')
@click.option('--sandbox/--real', '-s/-r', default=True)
@click.pass_context
def expire_hit_group(ctx, groupid, sandbox):
    click.echo(f'Expiring hit group {groupid} on MTurk')

    client = getClientFromProfile(ctx.obj['aws_profile'], sandbox=sandbox)
    wanted_hit_ids, _ = list_hits_with_groupid(client,groupid)

    for hit_id in wanted_hit_ids:
        client.update_expiration_for_hit(HITId=hit_id, ExpireAt=0)
        hit = client.get_hit(HITId=hit_id)
        new_expiry_date = hit['HIT']['Expiration']
        print(f"{hit_id} will now expire at {new_expiry_date}")

if __name__ == '__main__':
    cli()