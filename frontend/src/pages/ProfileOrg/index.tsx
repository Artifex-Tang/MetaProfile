import { GenericProfilePage } from '../ProfileGeneric'
import { orgService } from '../../api/profile'

export default function ProfileOrg() {
  return (
    <GenericProfilePage
      service={orgService}
      entityKey="org"
      idField="org_id"
      nameField="org_name_cn"
      label="机构"
    />
  )
}
