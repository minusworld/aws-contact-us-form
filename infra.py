import os
from troposphere import GetAtt
from troposphere import Ref
from troposphere import Template
from troposphere import Join
from troposphere import sns
from troposphere import awslambda
from troposphere import iam
from troposphere import apigatewayv2
from jinja2 import Template as jinja_template

domain = os.environ.get("EMAIL_CONTACT_DOMAIN", "test")
email_target = os.environ.get("EMAIL_TARGET", "test@email.com")
recaptcha_secret = os.environ.get("RECAPTCHA_SECRET")
cdomain = domain.replace(".", "-")

### SNS
send_to = sns.Subscription(
    Protocol="email",
    Endpoint=email_target
)

topic = sns.Topic(
    "EmailContactForm",
    Subscription=[send_to]
)

### Lambda
environment = {
    "ORIGIN_DOMAIN": domain,
    "TOPIC_ARN": Ref(topic)
}
if recaptcha_secret:
    environment["RECAPTCHA_SECRET"] = recaptcha_secret

lambda_environment = awslambda.Environment(
    Variables=environment
)

sns_publish_policy = iam.Policy(
    PolicyName=f"lambda-sns-publish-policy-contact-form-{cdomain}",
    PolicyDocument={
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": "sns:Publish",
            "Resource": "arn:aws:sns:*:*:*"
        }]
    },
)

lambda_logging_policy = iam.Policy(
    PolicyName=f"lambda-logging-policy-contact-form-{cdomain}",
    PolicyDocument={
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "logs:CreateLogGroup",
                "Resource": Join(
                    values=["arn", "aws", "logs", Ref("AWS::Region"), Ref("AWS::AccountId"), "*"],
                    delimiter=":"
                )
            },
            {
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": Join(
                    values=["arn", "aws", "logs", Ref("AWS::Region"), Ref("AWS::AccountId"), "log-group", "*"],
                    delimiter=":"
                )
            }
        ]
    }
)

role = iam.Role(
    "LambdaExecutionRole",
    Description=f"IAM Execution Role for contact form "
        f"lambda function on {domain}",
    RoleName=f"lambda-role-contact-form-{cdomain}",
    AssumeRolePolicyDocument={
        "Version": "2012-10-17",
        "Statement": {
            "Effect": "Allow",
            "Principal": {
                "Service": ["lambda.amazonaws.com"]
            },
            "Action": ["sts:AssumeRole"]
        }
    },
    Policies=[sns_publish_policy, lambda_logging_policy]
)

with open("lambda_handler.py", 'r') as fin:
    code = fin.read()

lambda_function = awslambda.Function(
    "LambdaHandler",
    FunctionName=f"lambda-handler-contact-form-{cdomain}",
    Description=f"Lambda function for contact form on {domain}",
    Environment=lambda_environment,
    Code=awslambda.Code(
        ZipFile=code
    ),
    Handler="index.lambda_handler",
    Runtime="python3.7",
    MemorySize=128,
    Role=GetAtt(role, "Arn")
)


### API Gateway
api = apigatewayv2.Api(
    "HttpApi",
    Name=f"api-contact-form-{cdomain}",
    Description=f"API Gateway for contact form on {domain}",
    ProtocolType="HTTP",
    Target=GetAtt(lambda_function, "Arn")
)

api_gateway_lambda_permission = awslambda.Permission(
    "ApiGatewayLambdaPermission",
    Action="lambda:InvokeFunction",
    FunctionName=GetAtt(lambda_function, "Arn"),
    Principal="apigateway.amazonaws.com",
    SourceArn=Join(
        values=["arn", "aws", "execute-api", Ref("AWS::Region"), Ref("AWS::AccountId"), 
            Join(values=[Ref(api), "*"], delimiter="/")],
        delimiter=":"
    )
)

t = Template()
t.add_resource(topic)
t.add_resource(role)
t.add_resource(lambda_function)
t.add_resource(api)
t.add_resource(api_gateway_lambda_permission)
print(t.to_yaml())