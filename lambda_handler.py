import base64
import boto3
import logging
import json
import os
import urllib
logger = logging.getLogger()
logger.setLevel(logging.INFO)

sns = boto3.client("sns")

def lambda_handler(event, context):
    body = event.get('body')
    body = base64.b64decode(body).decode('utf-8')
    body = urllib.parse.parse_qs(body)
    try:
        subject = "Contact Form - {}".format(body["name"])
        email = body["email"]
        message = "FROM: {}\n\n{}".format(email, body["message"])
    except KeyError as e:
        logger.error(e, exc_info=1)
        return {
            "statusCode": 400, 
            "body": json.dumps("Invalid form. Please fill out your name, email, and message."),
            "headers": {"Access-Control-Allow-Origin" : os.environ["ORIGIN_DOMAIN"]}
        }
    
    {% if "recaptcha_secret" in template_context %}
    try:
        recaptcha_response = body["g-recaptcha-response"]
        logger.debug("recaptcha_response: {}".format(recaptcha_response))
        postdata = urllib.parse.urlencode({
                "secret": os.environ["RECAPTCHA_SECRET"],
                "response": recaptcha_response
        })
        postdata = postdata.encode('ascii')
        with urllib.request.urlopen("https://www.google.com/recaptcha/api/siteverify", postdata) as fin:
            validation_response = fin.read().decode('utf-8')
        logger.debug(validation_response)
    except Exception as e:
        logger.error(e, exc_info=1)
        return {
            "statusCode": 401,
            "body": json.dumps("Must use ReCatpcha"),
            "headers": {"Access-Control-Allow-Origin" : os.environ["ORIGIN_DOMAIN"]}
        }

    if not json.loads(validation_response)["success"]:
        return {
            "statusCode": 401,
            "body": json.dumps("ReCaptcha failed. Are you a human?"),
            "headers": {"Access-Control-Allow-Origin" : os.environ["ORIGIN_DOMAIN"]}
        }
    {% endif %}

    try:
        mid = sns.publish(
            TopicArn=os.environ["TOPIC_ARN"],
            Subject=subject,
            Message=message
        )

        logger.info("message `{}` published to SNS: id={}".format(message, mid))
        return {
            "statusCode": 200, 
            "body": json.dumps("Message sent!"),
            "headers": {"Access-Control-Allow-Origin" : os.environ["ORIGIN_DOMAIN"]}
        }
    except Exception as e:
        logger.error(e, exc_info=1)
        return {
            "statusCode": 500, 
            "body": json.dumps("There was an error sending your message. Please send an email manually."),
            "headers": {"Access-Control-Allow-Origin" : os.environ["ORIGIN_DOMAIN"]}
        }
