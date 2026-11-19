import { readMessage } from "./messages.mjs";

export function comparisonCase(px4, ros, sharedClock) {
  return {
    schema: "attitude-atlas/comparison-v1",
    px4: px4.source,
    ros: ros.source,
    sharedClock,
  };
}
export function openCase(data) {
  if (
    data?.schema !== "attitude-atlas/comparison-v1" ||
    typeof data.sharedClock !== "boolean" ||
    data.px4 == null ||
    data.ros == null
  )
    throw Error("Expected an Attitude Atlas comparison-v1 case.");
  return {
    px4: readMessage(JSON.stringify(data.px4), "px4"),
    ros: readMessage(JSON.stringify(data.ros), "ros"),
    sharedClock: data.sharedClock,
  };
}
