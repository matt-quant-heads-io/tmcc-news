from pydantic import BaseModel, Field
from typing import List, Optional, Dict


class BloombergResponseObject(BaseModel):
    title: str = Field(description="The title of the news article")
    link: str = Field(default="", description="URL link to the article")
    published: str = Field(default="", description="Publication date and time")
    summary: str = Field(default="", description="Summary of the article")
    source: str = Field(description="Source URL of the RSS feed")
    
    @classmethod
    def from_feed_entry(cls, entry: Dict, source_url: str) -> "BloombergResponseObject":
        return cls(
            title=entry.get('title', ''),
            link=entry.get('link', ''),
            published=entry.get('published', ''),
            summary=entry.get('summary', ''),
            source=source_url
        )
    

class FMPResponseObject(BaseModel):
    title: str = Field(description="The title of the news article")
    link: str = Field(default="", description="URL link to the article")
    published: str = Field(default="", description="Publication date and time")
    summary: str = Field(default="", description="Summary of the article")
    source: str = Field(description="Source URL of the RSS feed")
    sources_to_ignore: List[str] = ["zacks.com", "seekingalpha"]
    
    @classmethod
    def from_feed_entry(cls, entry: Dict, source_url: str) -> "BloombergResponseObject":
        for src_to_ignore in cls.sources_to_ignore:
            if source_url.lower() in src_to_ignore.lower() or src_to_ignore.lower() in source_url.lower():
                return None

        return cls(
            title=entry.get('title', ''),
            link=entry.get('url', ''),
            published=entry.get('publishedDate', ''),
            summary=entry.get('text', ''),
            source=source_url
        )
    

class FMPPressReleaseResponseObject(BaseModel):
    title: str = Field(description="The title of the news article")
    link: str = Field(default="", description="URL link to the article")
    published: str = Field(default="", description="Publication date and time")
    summary: str = Field(default="", description="Summary of the article")
    source: str = Field(description="Source URL of the RSS feed")
    
    @classmethod
    def from_feed_entry(cls, entry: Dict, source_url: str) -> "BloombergResponseObject":    
        return cls(
            title=entry.get('title', ''),
            link=entry.get('url', ''),
            published=entry.get('date', ''),
            summary=entry.get('text', ''),
            source=source_url
        )
    

