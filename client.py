import re
import requests
import json
import logging


class Client(object):
    def __init__(self, config):
        self.site_url = config['site_url']
        self.token = config['token']
        self.auth_headers = {
            "Authorizations": f"Bearer {self.token}"
        }


class ListingRequestModifier(object):
    def __init__(self, page, item_per_page, ):
        pass

    def to_json(self):
        pass


class ResourceBase(object):

    def __init__(self, user, client):
        self.user = user
        self.client = client

    def get_url(self, name):
        raise NotImplementedError()

    def get_category_url(self):
        raise NotImplementedError()

    def get(self, name):
        resp = requests.get(self.get_url(name))
        logging.debug(f"Fetching {self.get_url(name)}")
        if resp.status_code == 200:
            logging.info(f"Found {self.get_url(name)}")
            return json.loads(resp.content.decode('utf-8'))
        elif resp.status_code == 404:
            logging.warning(f"{self.get_url(name)} return 404")
            return None
        else:
            raise ValueError(resp.status_code, resp.content.decode('utf-8'))

    def update(self, name, definition):
        logging.debug(f"Updating {self.get_url(name)}")
        resp = requests.post(self.get_url(name),
                             data=definition,
                             headers=self.client.auth_headers)
        if resp.status_code == 200:
            logging.info(f"Updated {self.get_url(name)}")
            return json.loads(resp.content.decode('utf-8'))
        elif resp.status_code == 404:
            logging.warning(f"Cannot find {self.get_url(name)}")
            return None
        else:
            raise ValueError(resp.status_code, resp.content.decode('utf-8'))

    def list(self):
        resp = requests.get(self.get_category_url(),
                            headers=self.client.auth_headers)
        if resp.status_code == 200:
            return json.loads(resp.content.decode('utf-8'))
        elif resp.status_code == 404:
            return None
        else:
            raise ValueError(resp.status_code, resp.content.decode('utf-8'))


class Instruction(ResourceBase):
    def get_url(self, name):
        url = f"{self.client.site_url}/api/instruction/{self.user}/{name}"
        return url

    def get_category_url(self):
        return f"{self.client.site_url}/api/instruction/{self.user}"


class Tutorial(ResourceBase):
    def get_url(self, name):
        url = f"{self.client.site_url}/api/tutorial/{self.user}/{name}"
        return url

    def get_category_url(self):
        return f"{self.client.site_url}/api/tutorial/{self.user}"


class QuestionSet(ResourceBase):
    def get_url(self, name):
        url = f"{self.client.site_url}/api/question_set/{self.user}/{name}"
        return url

    def get_category_url(self):
        return f"{self.client.site_url}/api/question_set/{self.user}"


class Exam(ResourceBase):

    def get_url(self, name):
        url = f"{self.client.site_url}/api/exam/{self.user}/{name}"
        return url

    def get_category_url(self):
        return f"{self.client.site_url}/api/exam/{self.user}"

    def list_responses(self, name):
        response_url = f"{self.client.site_url}/api/exam/{self.user}/{name}/response"
        resp = requests.get(response_url,
                            headers=self.client.auth_headers)
        if resp.status_code == 200:
            return json.loads(resp.content.decode('utf-8'))
        elif resp.status_code == 404:
            return None
        else:
            raise ValueError(resp.status_code, resp.content.decode('utf-8'))

    def get_responses(self, exam_id, response_ids):
        response_ids = "-".join([str(x) for x in response_ids])
        response_url = f"{self.client.site_url}/api/exam/{self.user}/{exam_id}/response/{response_ids}"
        resp = requests.get(response_url,
                            headers=self.client.auth_headers)
        if resp.status_code == 200:
            return json.loads(resp.content.decode('utf-8'))
        elif resp.status_code == 404:
            return None
        else:
            raise ValueError(resp.status_code, resp.content.decode('utf-8'))

    def get_report(self, name):
        report_url = f"{self.client.site_url}/api/exam/{self.user}/{name}/report"
        resp = requests.get(report_url,
                            headers=self.client.auth_headers)
        if resp.status_code == 200:
            return json.loads(resp.content.decode('utf-8'))
        elif resp.status_code == 404:
            return None
        else:
            raise ValueError(resp.status_code, resp.content.decode('utf-8'))


class Question(ResourceBase):

    def __init__(self, user, question_set_id, client):
        super().__init__(user, client)
        self.question_set_id = question_set_id

    def get_url(self, name):
        url = f"{self.client.site_url}/api/question_set/{self.user}/{self.question_set_id}/questions/{name}"
        return url

    def get_category_url(self):
        return f"{self.client.site_url}/api/question_set/{self.user}/{self.question_set_id}/questions"


def resolve_resource_with_name(url: str, client):
    """
    return: return url, resource_type, resource
    """
    if not url.startswith("/"):
        url = "/" + url

    name_pattern = "[a-zA-Z0-9_][a-zA-Z0-9-_]*"
    patterns = {
        "instruction": rf"^/instruction/(?P<user>{name_pattern})/(?P<name>{name_pattern})$",
        "tutorial": rf"^/tutorial/(?P<user>{name_pattern})/(?P<name>{name_pattern})$",
        "question_set": rf"^/question_set/(?P<user>{name_pattern})/(?P<name>{name_pattern})$",
        "question": rf"^/question_set/(?P<user>{name_pattern})/(?P<question_set_id>{name_pattern})/(?P<question_id>{name_pattern})$",
        "exam": rf"^/exam/(?P<user>{name_pattern})/(?P<exam_id>{name_pattern})$",
    }

    for resource_type, pattern in patterns.items():
        match = re.match(pattern, url)
        if match:
            if resource_type == "instruction":
                return Instruction(match.group('user'), client), resource_type, match.group('name')
            if resource_type == "tutorial":
                return Tutorial(match.group('user'), client), resource_type, match.group('name')
            if resource_type == "question_set":
                return QuestionSet(match.group('user'), client), resource_type, match.group('name')
            if resource_type == "question":
                return QuestionSet(match.group('user'), client), resource_type, match.group('name')
            if resource_type == "exam":
                return Exam(
                    user=match.group('user'),
                    client=client), resource_type, match.group('exam_id')
    raise ValueError(f"Cannot parse Resource identifier {url}")


def resolve_resource(url: str, client):
    """
    return: return url, resource_type
    """
    if not url.startswith("/"):
        url = "/" + url

    name_pattern = "[a-zA-Z0-9_][a-zA-Z0-9-_]*"

    patterns = {
        "instruction": rf"^/instruction/(?P<user>{name_pattern})$",
        "tutorial": rf"^/tutorial/(?P<user>{name_pattern})$",
        "question_set": rf"^/question_set/(?P<user>{name_pattern})$",
        "question": rf"^/question_set/(?P<user>{name_pattern})/questions$",
        "exam": rf"^/exam/(?P<user>{name_pattern})$",
    }

    for resource_type, pattern in patterns.items():
        match = re.match(pattern, url)
        if match:
            if resource_type == "instruction":
                return Instruction(match.group('user'), client), resource_type
            if resource_type == "tutorial":
                return Tutorial(match.group('user'), client), resource_type
            if resource_type == "exam":
                return Exam(match.group('user'), client), resource_type
            if resource_type == "exam":
                return Exam(
                    user=match.group('user'),
                    exam_id=match.group('exam_id'),
                    client=client), resource_type
    raise ValueError(f"Cannot parse Resource identifier {url}")
