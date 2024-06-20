# import necessary libraries
import csv
import isodate
import logging
import re

import pandas as pd
import pytz
from bs4 import (
    BeautifulSoup,
)  # for parsing data from html file of YouTube Watch History
from googleapiclient.discovery import build
from datetime import datetime


def main():
    html_file_path = "watch-history.html"
    # The output file as csv
    youtube_data = "youtube_data.csv"
    # Call function to extract preliminary data from the hmtl file
    extract_data_from_html(html_file_path, youtube_data)
    # Call function to extract additional data from the YouTube API
    extract_data_from_api(youtube_data)

    print("Data extraction completed.")


def extract_data_from_html(html_file_path: str, csv_output_path: str) -> None:
    """
    This function takes an HTML file and extracts preliminary data from it: the title of the video and its URL,
    watch date, channel uploader, and its URL. Then it will return a CSV file storing the extracted data.

    :param html_file_path: The path to the HTML file to be parsed.
    :param csv_output_path: The path where the output CSV file should be saved.
    :return: None
    """

    # Read the HTML file
    with open(html_file_path, "r", encoding="utf-8") as file:
        html_content = file.read()

    # Parse the HTML content with BeautifulSoup
    soup = BeautifulSoup(html_content, "html.parser")

    # Store extracted information in a list of dictionaries
    videos_data = []

    # Find html elements containing the video information
    video_elements = soup.find_all(
        "div", class_="content-cell mdl-cell mdl-cell--6-col mdl-typography--body-1"
    )

    # Extract each video data founded for each HTML elements
    for video in video_elements:
        # Find the first <a> tag for the title and URL
        title_element = video.find("a")
        title = title_element.text.strip() if title_element else None

        """
        Handle case where there is no video title extracted from the HTML element due to:
        (1) the video being removed/deleted from YouTube, or (2) the element being a YouTube Ad.
        In such cases, we skip to the next HTML element and do not include videos with missing information.
        """
        if not title or (
            match := re.search(
                r"https?://(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]+)", title
            )
        ):
            logging.warning("No title found for a video element.")
            continue  # Skip to the next video element

        url = title_element["href"] if title_element else None

        # Initialize default values for channel name and date time
        channel_name = channel_url = date_time = None

        # additional data
        video_date_upload = video_views = video_likes = video_dislikes = (
            video_comment_count
        ) = video_description = video_tags = video_duration = None

        # Find the second <a> tag for the channel name
        if title_element:
            channel_element = title_element.find_next("a")
            if channel_element:
                channel_name = channel_element.text.strip()
                channel_url = channel_element["href"]

                # Find the date and time, which is the text after the channel link
                date_time_element = channel_element.find_next_sibling(string=True)
                if date_time_element:
                    date_time = date_time_element.strip()
                    cleaned_date_time = clean_date_time(date_time)

        videos_data.append(
            {
                "title": title,
                "url": url,
                "video_duration": video_duration,
                "channel_name": channel_name,
                "channel_url": channel_url,
                "date_time": date_time,
                "video_date_upload": video_date_upload,
                "video_views": video_views,
                "video_likes": video_likes,
                "video_dislikes": video_dislikes,
                "video_comment_count": video_comment_count,
                "video_description": video_description,
                "video_tags": video_tags,
            }
        )

    # Write the data to a CSV file
    with open(csv_output_path, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = [
            "title",
            "url",
            "video_duration",
            "channel_name",
            "channel_url",
            "date_time",
            "video_date_upload",
            "video_views",
            "video_likes",
            "video_dislikes",
            "video_comment_count",
            "video_description",
            "video_tags",
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        # Write header
        writer.writeheader()

        # Write video data
        for video in videos_data:
            writer.writerow(video)

    print(f"Scraped data saved to {csv_output_path}")


def extract_data_from_api(youtube_data: str) -> None:  # Set up logging
    """
    This function takes a pre-existing CSV file that already contains some video information extracted from an HTML file.
    It iterates through each video in the CSV, requests additional information from the YouTube API,
    and then saves this information back to the CSV file.

    :param youtube_data: csv file where preliminary data is stored.
    :return: None
    """

    # Set up logging
    logging.basicConfig(level=logging.DEBUG)

    # Set up YouTube API client
    youtube = build(
        "youtube", "v3", developerKey="AIzaSyASJ2J8veRMGEUs69uvkRpGRhomjCyePsA"
    )

    # Read the csv file to iterate on every YouTube Video
    with open(youtube_data, "r", newline="", encoding="latin-1") as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            # Access values by column names (keys in the dictionary)
            video_url = row["url"]

            if video_url is not None:
                print("Video Url:", video_url)
                logging.debug("Processing video URL: %s", video_url)
            else:
                logging.warning("Encountered None value for video URL")

            video_id = extract_video_id(video_url)

            if video_id:
                try:
                    # Make API request to retrieve detailed video information
                    video_response = (
                        youtube.videos()
                        .list(part="snippet,contentDetails,statistics", id=video_id)
                        .execute()
                    )

                    # Extract additional details from video response
                    if "items" in video_response and video_response["items"]:
                        video_info = video_response["items"][0]["snippet"]
                        video_content_details = video_response["items"][0][
                            "contentDetails"
                        ]
                        video_stats = video_response["items"][0].get("statistics", {})

                        # read the csv file
                        df = pd.read_csv(youtube_data)
                        # locate each video url and update the returned data from API
                        df.loc[
                            df["url"] == video_url,
                            [
                                "video_date_upload",
                                "video_views",
                                "video_likes",
                                "video_dislikes",
                                "video_comment_count",
                                "video_description",
                                "video_tags",
                                "video_duration",
                            ],
                        ] = (
                            str(
                                process_datetime(video_info.get("publishedAt", ""))
                            ),  # Assuming video_date_upload is a string
                            int(
                                video_stats.get("viewCount", 0)
                            ),  # Assuming video_views is an integer
                            int(
                                video_stats.get("likeCount", 0)
                            ),  # Assuming video_likes is an integer
                            int(
                                video_stats.get("dislikeCount", 0)
                            ),  # Assuming video_dislikes is an integer
                            int(
                                video_stats.get("commentCount", 0)
                            ),  # Assuming video_comment_count is an integer
                            str(
                                video_info.get("description", "")
                            ),  # Assuming video_description is a string
                            ",".join(
                                video_info.get("tags", "")
                            ),  # Assuming video_tags is a string
                            str(
                                clean_duration_time(
                                    video_content_details.get("duration", "")
                                )
                            ),
                            # Assuming video_duration is a string
                        )

                        df.to_csv(youtube_data, index=False)
                    else:
                        logging.warning(
                            "No video items found in the response for video ID: %s",
                            video_id,
                        )
                except Exception as e:
                    logging.warning(
                        "An error occurred while processing video ID %s: %s",
                        video_id,
                        e,
                    )
            else:
                logging.warning("Failed to extract video ID from URL: %s", video_url)


def extract_video_id(video_url):
    if video_url and "https://www.youtube.com/watch?v=" in video_url:
        return video_url.replace("https://www.youtube.com/watch?v=", "")
    else:
        logging.warning("Invalid or missing video URL: %s", video_url)
        return None


def clean_duration_time(duration: str) -> str:
    """
    Cleans and formats an ISO 8601 duration string into a readable time format.

    :param duration: A string representing the ISO 8601 duration (e.g., 'PT1H2M3S').
    :return: A string formatted as 'HH:MM:SS'.

    Example:
    >>> clean_duration_time('PT1H2M3S')
    '01:02:03'
    >>> clean_duration_time('PT15M25S')
    '00:15:25'
    """

    # Parse the ISO 8601 duration
    duration = isodate.parse_duration(duration)
    total_seconds = int(duration.total_seconds())

    # Calculate hours, minutes, and seconds
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    # Return formatted string
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def process_datetime(datetime_str):
    """
    Cleans and formats an ISO 8601 duration string into a readable time format.

    :param datetime_str: A string representing the ISO 8601 duration (e.g., '2017-11-13T06:06:22Z').
    :return: A string formatted as 'YYYY-MM-DD HH:MM:SS'.

    Example:
    >>> process_datetime('2017-11-13T06:06:22Z')
    2017-11-13 06:06:22
    >>> process_datetime('2020-04-10T05:36:02Z')
    '2020-04-10 05:36:02'
    """
    # Parse the datetime string into a datetime object
    dt = datetime.fromisoformat(datetime_str)

    # Format the datetime object as per requirement
    formatted_datetime = dt.strftime("%Y-%m-%d %H:%M:%S")

    return formatted_datetime


def clean_date_time(date_time):
    # Replace any non-ASCII characters with an empty string
    cleaned_date_time = "".join(char for char in date_time if ord(char) < 128)
    # Add any additional cleaning or formatting logic here if needed
    if "PM" in cleaned_date_time:
        return cleaned_date_time.replace("PM", " PM")
    return cleaned_date_time.replace("AM", " AM")


if __name__ == "__main__":
    main()
