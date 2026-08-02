import { Link } from "react-router";

import { ActionFeedbackComponent } from "../../../shared/feedback/ActionFeedbackComponent";
import { PairingPageFrameComponent } from "../components/PairingPageFrameComponent";

export function PairingCompletionPageRegion({ message }: { message: string }) {
  return <PairingPageFrameComponent><div className="form-action-row">
    <ActionFeedbackComponent state={{ pending: false, message }} />
    <div className="form-actions"><Link className="button button--secondary" to="/">Go to Home</Link><Link className="button" to="/profile">Back to Profile</Link></div>
  </div></PairingPageFrameComponent>;
}
