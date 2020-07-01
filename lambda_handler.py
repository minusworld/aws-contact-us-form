import base64
import boto3
import logging
import json
import os
import urllib
logger = logging.getLogger()
logger.setLevel(logging.INFO)

sns = boto3.client("sns")

def parse_event(event):
    body = event.get("body", "")
    content_type = event.get("headers", {}).get("content-type", "text/plain")
    is_base64 = event.get("isBase64Encoded", False)
    if is_base64:
        body = base64.b64decode(body).decode('utf-8')
    if content_type == "application/x-www-form-urlencoded":
        # For some reason, everything is a list when using parse_qs. De-listify:
        return {k: v[0] for k, v in urllib.parse.parse_qs(body).items()}
    elif content_type == "application/json":
        return json.loads(body)
    else:
        return body

def lambda_handler(event, context):
    body = parse_event(event)
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

    if "RECAPTCHA_SECRET" in os.environ:  # Validate recaptcha if it exists
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
