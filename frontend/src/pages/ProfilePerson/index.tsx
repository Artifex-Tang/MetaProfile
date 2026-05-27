import { GenericProfilePage } from '../ProfileGeneric'
import { personService } from '../../api/profile'

export default function ProfilePerson() {
  return (
    <GenericProfilePage
      service={personService}
      entityKey="person"
      idField="person_id"
      nameField="name_cn"
      label="人员"
    />
  )
}
