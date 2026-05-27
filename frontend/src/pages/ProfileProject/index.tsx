import { GenericProfilePage } from '../ProfileGeneric'
import { projectService } from '../../api/profile'

export default function ProfileProject() {
  return (
    <GenericProfilePage
      service={projectService}
      entityKey="project"
      idField="project_id"
      nameField="project_name_cn"
      label="项目"
    />
  )
}
