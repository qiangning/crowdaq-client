import boto3
import string
import random

MTURK_SANDBOX = 'https://mturk-requester-sandbox.us-east-1.amazonaws.com'
MTURK_PROD = 'https://mturk-requester.us-east-1.amazonaws.com'

def getClientFromProfile(profile, sandbox=False):
    return boto3.Session(profile_name=profile).client('mturk', endpoint_url=MTURK_SANDBOX if sandbox else MTURK_PROD)

def get_client_from_accessfile(access_file, sandbox=False):
    access_key_info = open(access_file).readlines()
    access_key, secret_access_key = access_key_info[-1].strip().split(",")
    return boto3.client('mturk',
                        aws_access_key_id=access_key,
                        aws_secret_access_key=secret_access_key,
                        region_name='us-east-1',
                        endpoint_url=MTURK_SANDBOX if sandbox else MTURK_PROD
                        )

def randomString(stringLength):
    """Generate a random string with the combination of lowercase and uppercase letters """

    letters = string.ascii_letters
    return ''.join(random.choice(letters) for i in range(stringLength))

def get_workerids_with_qualification_type(client, qid):
    workers_union = set()
    response = client.list_workers_with_qualification_type(
        QualificationTypeId=qid,
        MaxResults=100
    )
    workers_union = workers_union.union(set([x['WorkerId'] for x in response['Qualifications']]))
    while 'NextToken' in response:
        response = client.list_workers_with_qualification_type(
            QualificationTypeId=qid,
            MaxResults=100,
            NextToken=response['NextToken']
        )
        workers_union = workers_union.union(set([x['WorkerId'] for x in response['Qualifications']]))
    return list(workers_union)


def get_all_hits(client, qual_id=''):
    if qual_id == '':
        list_hits_response = client.list_hits(MaxResults=100)
    else:
        list_hits_response = client.list_hits_for_qualification_type(MaxResults=100,
                                                                     QualificationTypeId=qual_id)
    all_hits = list_hits_response['HITs']
    while 'NextToken' in list_hits_response:
        if qual_id == '':
            list_hits_response = client.list_hits(MaxResults=100,
                                                  NextToken=list_hits_response['NextToken'])
        else:
            list_hits_response = client.list_hits_for_qualification_type(MaxResults=100,
                                                                         NextToken=list_hits_response['NextToken'],
                                                                         QualificationTypeId=qual_id)
        all_hits += list_hits_response['HITs']
    return all_hits


def list_hits_with_groupid(client, group_id, qual_id=''):
    all_hits = get_all_hits(client, qual_id)
    wanted_hits = [hit for hit in all_hits if hit['HITGroupId'] == group_id]
    wanted_hit_ids = [hit['HITId'] for hit in wanted_hits]

    if not wanted_hits:
        print(f"[Warning] No HITs found in group: {group_id}")

    return wanted_hit_ids, wanted_hits


def get_all_assignments_of_hit(client, hit_id):
    assignments = []
    response = client.list_assignments_for_hit(
        HITId=hit_id,
        MaxResults=100,
        AssignmentStatuses=[
            'Submitted', 'Approved',
        ]
    )
    assignments += response['Assignments']
    while 'NextToken' in response:
        response = client.list_assignments_for_hit(
            HITId=hit_id,
            MaxResults=100,
            AssignmentStatuses=[
                'Submitted', 'Approved',
            ],
            NextToken=response['NextToken']
        )
        assignments += response['Assignments']

    assignment_ids = [x['AssignmentId'] for x in assignments]
    return assignment_ids, assignments

def grant_qualification_to_workers(client, qual_id, work_ids, dryrun=True, verbose=True):
    if dryrun:
        verbose = True
    for wid in work_ids:
        try:
            if not dryrun:
                response = client.associate_qualification_with_worker(
                    QualificationTypeId=qual_id,
                    WorkerId=wid,
                    IntegerValue=1,
                    SendNotification=False
                )
            if dryrun:
                print('Dry run:')
            if verbose:
                print(f'{wid} qualified for qualification type {qual_id}')
        except:
            print(f'Failed to qualify {wid} for qualification type {qual_id}')


def grant_new_qualification_to_workers(client, workids, dryrun=True):
    random_str = randomString(10)
    response = client.create_qualification_type(Name=random_str, Description=random_str,
                                                QualificationTypeStatus='Active')
    qual_id = response['QualificationType']['QualificationTypeId']
    grant_qualification_to_workers(client, qual_id, workids, dryrun)


def remove_qualification_from_workers(client, qual_id, work_ids, dryrun=True):
    for wid in work_ids:
        try:
            if not dryrun:
                response = client.disassociate_qualification_from_worker(
                    QualificationTypeId=qual_id,
                    WorkerId=wid,
                )
            print(f'{wid} disassociates with qualification type {qual_id}')
        except:
            print(f'Failed to disassociates {wid} with qualification type {qual_id}')


def remove_all_workers_in_qualfication(client, qual_id, dryrun=True):
    workers = get_workerids_with_qualification_type(client, qual_id)
    remove_qualification_from_workers(client, qual_id, workers, dryrun)