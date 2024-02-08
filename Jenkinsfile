// declarative pipeline
pipeline {
    agent any
    environment {
        JENKINS_JSON_CONFIG = "${params.JSONConfig}"
        JENKINS_API_KEY = credentials("${params.ApiKeyName}")
    }
    stages {
        stage('Prepare workspace') {
            steps {
                cleanWs()
                git branch: 'main', url: 'http://github.com/token47/sunbeam-ci.git'
                sh "ls -la"
                sh "cat Jenkinsfile"
            }
        }
        stage('Prepare substrate') {
            steps {
                sh "./prepare_substrate.py"
            }
        }
        stage('Deploy Sunbeam') {
            steps {
                sh "./deploy_sunbeam.py"
            }
        //    post {
        //        failure {
        //            script {
        //                if (params.PauseBuild) {
        //                    input message:"Paused. Continue?"
        //                }
        //            }
        //        }
        //    }
        //}
        //stage('Test Sunbeam') {
        //    steps {
        //        sh "./test_sunbeam.py"
        //    }
            post {
                always {
                    script {
                        if (params.PauseBuild) {
                            input message:"Paused. Continue?"
                        }
                    }
                }
            }
        }
    }
    post {
        always {
            sh "./destroy_substrate.py"
        }
    }
}