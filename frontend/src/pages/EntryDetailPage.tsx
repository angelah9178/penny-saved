import { Link, useParams } from "react-router-dom";

import { ApiError } from "../api/errors";
import { DateTime } from "../components/DateTime";
import { ErrorAlert } from "../components/ErrorAlert";
import { Loading } from "../components/Loading";
import { CommentEditor } from "../features/entries/CommentEditor";
import {
  useEntryDetail,
  useUpdateEntryCommentMutation,
} from "../features/entries/queries";
import { formatUsd } from "../lib/currency";

export function EntryDetailPage() {
  const { entryId = "" } = useParams();
  const detail = useEntryDetail(entryId);
  const updateComment = useUpdateEntryCommentMutation(entryId);

  if (detail.isPending) return <Loading message="Loading entry…" />;

  if (detail.isError) {
    return (
      <div className="entry-detail-page">
        <h1>Entry details</h1>
        <ErrorAlert
          message={detailErrorMessage(detail.error)}
          onRetry={() => void detail.refetch()}
        />
        <Link to="/dashboard">Back to dashboard</Link>
      </div>
    );
  }

  const entry = detail.data.entry;
  const resolved = entry.status === "saved" || entry.status === "purchased";

  return (
    <div className="entry-detail-page">
      <h1>{entry.item_name}</h1>
      <dl className="entry-detail-list">
        <div>
          <dt>Price</dt>
          <dd>{formatUsd(entry.price_cents)}</dd>
        </div>
        <div>
          <dt>Reason wanted</dt>
          <dd>{entry.reason_wanted}</dd>
        </div>
        <div>
          <dt>Result</dt>
          <dd>{entry.status}</dd>
        </div>
        <div>
          <dt>Recorded</dt>
          <dd>
            <DateTime value={entry.created_at} />
          </dd>
        </div>
        {entry.checked_in_at === null ? null : (
          <div>
            <dt>Checked in</dt>
            <dd>
              <DateTime value={entry.checked_in_at} />
            </dd>
          </div>
        )}
      </dl>

      {resolved ? (
        <section aria-labelledby="comment-editor-title">
          <h2 id="comment-editor-title">Edit comment</h2>
          <p>
            Update or clear the reflection without changing the purchase result.
          </p>
          <CommentEditor
            comment={entry.comment}
            onSubmit={(payload) => updateComment.mutateAsync(payload)}
          />
        </section>
      ) : (
        <div className="request-state request-state--empty">
          <p>Comments can be edited after this entry is saved or purchased.</p>
        </div>
      )}
      <Link to="/dashboard">Back to dashboard</Link>
    </div>
  );
}

function detailErrorMessage(error: Error): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return "We could not find that entry.";
    if (error.status === 403) return "You do not have access to that entry.";
  }
  return "We could not load this entry. Please try again.";
}
