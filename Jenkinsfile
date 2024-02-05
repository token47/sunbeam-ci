pipeline {
    agent any
    environment {
        JENKINS_JSON_CONFIG = params.JSONConfig
        JENKINS_API_KEY = credentials(params.ApiKeyName)
    }
    stages {
        stage('Prepare workspace') {
            cleanWs()
            git branch: 'main', url: 'http://github.com/token47/sunbeam-ci.git'
            sh "ls -la"
        }
        stage('Prepare substrate') {
            sh "./prepare_substrate.py"
        }
        stage('Deploy Sunbeam') {
            sh "./deploy_sunbeam.py"
        }
        stage('Maybe Pause the Build') {
            if (params.PauseBuild) {
                input message:"Ready to continue Build?"
            }
        }
    }
    post {
        always {
            sh "./destroy_substrate.py"
        }
    }
}