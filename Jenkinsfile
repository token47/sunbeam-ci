pipeline {
    agent any
    stages {
        stage('Get maas machines') {
            steps {
                sh "maas_machines.sh"
            }
        }
    }
}
