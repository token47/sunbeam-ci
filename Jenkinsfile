pipeline {
    agent any
    stages {
        stage('Prepare substrate') {
            steps {
                sh "./prepare_substrate.py"
            }
        }
        stage('Deploy Sunbeam') {
            steps {
                sh "./deploy_sunbeam.py"
            }
        }
    }
}
