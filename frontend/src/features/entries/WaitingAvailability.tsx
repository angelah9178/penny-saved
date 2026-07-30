import { DateTime } from "../../components/DateTime";

export type WaitingAvailabilityProps = {
  eligibleForCheckInAt: string;
};

export function WaitingAvailability({
  eligibleForCheckInAt,
}: WaitingAvailabilityProps) {
  return (
    <span>
      Check-in available{" "}
      <DateTime
        value={eligibleForCheckInAt}
        fallback="when the waiting period ends"
      />
    </span>
  );
}
